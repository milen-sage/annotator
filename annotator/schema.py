from __future__ import unicode_literals
import os
import requests
from requests.auth import HTTPBasicAuth
import json
import pandas as pd
from . import utils



def getAnnotationsRelease():
    """

    Returns
    -------
    the latest release version of Sage Bionetworks annotations on github
    """
    reqRelease = requests.get("https://api.github.com/repos/Sage-Bionetworks/synapseAnnotations/releases")
    releaseVersion = reqRelease.json()[0]['tag_name']
    return releaseVersion


def moduleJsonPath(releaseVersion=None):
    """ get and load the list of json files from data folder (given the api endpoint url - ref master - latest vesion)
     then construct a dictionary of module names and its associated raw data github url endpoints.

    Parameters
    ----------
    releaseVersion : str
    Optional. github release version of annotations

    Returns
    -------
    Python dictionary of module name keys and the release version path to its module raw github json URL as values

    example {u'analysis':
             u'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/analysis.json',
            ... } @kenny++
    """
    if releaseVersion is None:
        releaseVersion = getAnnotationsRelease()

    gitPath = 'https://api.github.com/repos/Sage-Bionetworks/synapseAnnotations/contents/synapseAnnotations/data/?ref='
    req = requests.get(gitPath + releaseVersion) 
    file_list = json.loads(req.content)
    names = {os.path.splitext(x['name'])[0]: x['download_url'] for x in file_list}

    return names


def flattenJson(path, module=None):
    """Normalize semi-structured JSON schema data into a flat table.

    Parameters
    ----------
    path : str
        Path to JSON file. Can be a url or filepath.
    module : str
        Optional. Module from which json schema is derived from.

    Returns
    -------
    pd.DataFrame
    """
    json_record = pd.read_json(path)

    # grab annotations with empty enumValue lists
    # i.e. don't require normalization and structure their schema
    empty_vals = json_record.loc[json_record.enumValues.str.len() == 0]
    empty_vals = empty_vals.drop('enumValues', axis=1)
    empty_vals['valueDescription'] = ""
    empty_vals['source'] = ""
    empty_vals['value'] = ""
    empty_vals['module'] = module
    empty_vals.set_index(empty_vals['name'], inplace=True)

    # for each value list object
    flatten_vals = []
    json_record = json_record.loc[json_record.enumValues.str.len() > 0]
    json_record.reset_index(inplace=True)

    for i, jsn in enumerate(json_record['enumValues']):
        normalized_values_df = pd.io.json.json_normalize(jsn)

        # re-name 'description' defined in dictionary to valueDescription
        # to match table on synapse schema
        normalized_values_df = normalized_values_df.rename(
                columns={'description': 'valueDescription'})

        # grab key information in its row, expand it by values dimension
        # and append its key-columns to flattened values
        rows = json_record.loc[[i], json_record.columns != 'enumValues']
        repeats = pd.concat([rows] * len(normalized_values_df.index))
        repeats.set_index(normalized_values_df.index, inplace=True)
        flatten_df = pd.concat([repeats, normalized_values_df], axis=1)
        # add column module for annotating the annotations
        flatten_df['module'] = module
        '''
         hacky ... script assumes unique column names... our json model doesn't enforce/require that; might need to change assumptions or json model
        '''
        if list(flatten_df.columns).count("name") > 1:
            flatten_df.columns = ['index', 'columnType', 'description', 'maximumSize', 'name', 'valueDescription', 'value', 'source', 'module'] 

        flatten_df.set_index(flatten_df['name'], inplace=True)
        flatten_vals.append(flatten_df)

    flatten_vals.append(empty_vals)
    module_df = pd.concat(flatten_vals, sort = False)
    module_df = module_df.rename(columns={'name': 'key'})
    return module_df


def validateView(view, schema, syn=None):
    """ Check that a view conforms with a schema.

    Parameters
    ----------
    view : pandas DataFrame, str
        A DataFrame or Synapse ID -- anything that can be read by
        utils.synread.
    schema : pandas DataFrame, str
        A DataFrame in flattened schema format (see flattenJson) or
        path to .json file.
    syn : synapseclient.Synapse
        Optional. A Synapse object for retreiving `view` from Synapse.
        Defaults to None.

    Returns
    -------
    dict of malformed values.
    """
    view = utils.synread(syn, view)
    schema = flattenJson(schema) if isinstance(schema, str) else schema
    to_examine = schema.index.intersection(view.columns)
    malformed = {}
    for k in to_examine:
        allowed_vals = set(schema.loc[k].value)
        actual_vals = set(view.loc[:,k].unique())
        malformed_vals = actual_vals.difference(allowed_vals)
        if malformed_vals:
            malformed[k] = malformed_vals
    return malformed
