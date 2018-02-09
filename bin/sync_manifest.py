#!/usr/bin/env python
"""
Create Synapse sync manifest
"""
import os
import sys
import json
from six.moves.urllib.parse import urlparse
from six.moves.urllib.request import urlopen
import pandas
import synapseclient
import synapseutils


def _getLists(local_root, depth):
    """
    Given a depth, creates a list of directory and files hierarchy paths.

    :param local_root:
    :param depth:
    :return:
    """
    dir_list = []
    file_list = []

    for dirpath, _, filenames in os.walk(local_root):

        sub_dir = dirpath[len(local_root):]
        n = sub_dir.count(os.path.sep) + 1 if sub_dir != '' else 0
        dirpath = os.path.abspath(dirpath)

        if depth is not None:
            if n < depth:
                dir_list.append(dirpath)
        else:
            dir_list.append(dirpath)

        for name in filenames:
            if not name.startswith('.'):
                file_list.append(os.path.join(dirpath, name))

    return dir_list, file_list


def _getSynapseDir(syn, synapse_id, local_root, dir_list):
    """
    Walks through Synapse parent location hierarchy.
    update folders in Synapse to match the local dir,
    get key-value pairs of dirname and synapse id

    :param syn:
    :param synapse_id:
    :param local_root:
    :param dir_list:
    :return:
    """
    synapse_dir = {}
    synapse_root = syn.get(synapse_id)

    for (dirpath, dirpath_id), _, _ in synapseutils.walk(syn, synapse_id):
        dirpath = dirpath.replace(synapse_root.name, os.path.abspath(local_root))
        synapse_dir[dirpath] = dirpath_id

    for directory in dir_list:

        if not synapse_dir.has_key(directory):
            new_folder = synapseclient.Folder(os.path.basename(directory),
                                              synapse_dir[os.path.dirname(directory)])
            new_folder = syn.store(new_folder)
            synapse_dir[directory] = new_folder.id

    return synapse_dir


def _getAnnotationKey(dirs):
    """
     Get the list of annotation keys (manifest columns)

    :param dirs:
    :return:
    """
    key_list = ['used', 'executed']

    if dirs is not None:

        for directory in dirs:

            if urlparse(directory).scheme != '':
                jfile = urlopen(directory)
            else:
                jfile = open(directory, 'r')

            base, ext = os.path.splitext(os.path.basename(directory))

            if ext == '.json':
                data = json.load(jfile)
            else:
                sys.stderr.write('File %s cannot be parsed. JSON format is required.\n' % directory)

            data = pandas.DataFrame(data)
            annotation_key = data['name']
            key_list = key_list + list(annotation_key)

    return key_list


def _getName(path, synapse_dir, local_root, depth):
    """
    Finds the name of files in local directory.

    :param path:
    :param synapse_dir:
    :param local_root:
    :param depth:
    :return: name of file and it's associated parent location/benefactor
    """
    path_no_root = path[len(os.path.abspath(local_root)):]

    if depth is not None and path_no_root.count(os.path.sep) > depth - 1:

        if str.startswith(path_no_root, '/'):
            path_no_root = path_no_root[1:]

        temp_name = path_no_root.split('/')[(depth - 1):]
        name = '_'.join(temp_name)

        temp_name = '/'.join(temp_name)
        parent = synapse_dir[os.path.dirname(path[:-len(temp_name)])]
    else:
        name = os.path.basename(path)
        parent = synapse_dir[os.path.dirname(path)]
        
    return name, parent


def create(file_list, key_list, synapse_dir, local_root, depth, tab):
    """
    Creates manifest designed for the input of sync function.

    :param file_list:
    :param key_list:
    :param synapse_dir:
    :param local_root:
    :param depth:
    :param tab:
    :return:
    """

    result = pandas.DataFrame()
    result['path'] = file_list
    result['name'] = ""
    result['parent'] = ""

    for index, row in result.iterrows():
        row[['name', 'parent']] = _getName(row['path'], synapse_dir, local_root, depth)

    cols = list(result.columns)

    result = pandas.concat([result, pandas.DataFrame(columns=key_list)])
    # reorder the columns
    result = result[cols + key_list]

    if tab:
        # cat the tab delaminated manifest into sys.stdout for piping
        result.to_csv(sys.stdout, sep="\t", index=False)
    else:
        result.to_csv('annotations_manifest.csv', sep=",", index=False)
        sys.stderr.write('Manifest has been created.\n')


def main():
    import argparse
    syn = synapseclient.login(silent=True)

    parser = argparse.ArgumentParser(description="Creates a manifest (filepath by annotations) designed for the input "
                                                 "of synapse sync function to facilitate file organization and "
                                                 "annotations of those files on synapse.")
    parser.add_argument('-d', '--directory', help='local directory with files and folders hierarchy to be mirrored on '
                                                  'synapse.', required=True)
    parser.add_argument('--id', help='Project/folder synapse id that will mirror the file organization hierarchy. '
                                     'This information would be placed in manifest parent column and would be used to '
                                     'allocate the parent directory on synapse after sync function has been run.',
                        required=True)
    parser.add_argument('-f', '--files',
                        help='Path(s) to JSON file(s) of annotations (optional)', nargs='+', required=False)
    parser.add_argument('-n', '--n', help='Depth of hierarchy (default: %{default}) or number of nested folders to '
                                          'mirror. Any file/folder beyond this number would be expanded into the '
                                          'hierarchy number indicated.', default=None, required=False)
    parser.add_argument('--tab', action='store_true', help='tab delaminated manifest will be echoed into standard '
                                                           'output for piping', required=False)

    args = parser.parse_args()

    sys.stderr.write('Preparing to create manifest\n')
    local_root = args.directory
    synapse_id = args.id
    annotations = args.files
    depth = args.n
    tab = args.tab

    if depth is not None:
        depth = int(depth)

    dir_list, file_list = _getLists(local_root, depth)

    synapse_dir = _getSynapseDir(syn, synapse_id, local_root, dir_list)
    key_list = _getAnnotationKey(annotations)

    create(file_list, key_list, synapse_dir, local_root, depth, tab)

if __name__ == '__main__':
    main()
