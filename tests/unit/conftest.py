import pytest
import sys
import logging
import pandas
import synapseclient
import uuid


SAMPLE_FILE = "../sampleFile.csv"
SAMPLE_META = "../sampleMeta.csv"


@pytest.fixture(scope='session')
def syn():
    syn = synapseclient.login()
    return syn


@pytest.fixture(scope='session')
def sampleEntities():
    data = pandas.read_csv(SAMPLE_FILE, header=0, index_col=None)
    meta = pandas.read_csv(SAMPLE_META, header=0, index_col=None)
    return {'data': data, 'meta': meta}


@pytest.fixture(scope='session')
def project(syn):
    project = synapseclient.Project(str(uuid.uuid4()))
    project = syn.store(project)
    yield project
    syn.delete(project)


def _entity_view(syn_, project_):
    entity_view = synapseclient.EntityViewSchema(
            name=str(uuid.uuid4()),
            parent=project_,
            scopes=[project_])
    entity_view = syn_.store(entity_view)
    return entity_view


@pytest.fixture
def entity_view(syn, project):
    entity_view = _entity_view(syn, project)
    return entity_view

@pytest.fixture(scope='session')
def entities(syn, sampleEntities, project):
    # store sample files
    _file = synapseclient.File(path=SAMPLE_FILE, name='file1.csv',
                               parent=project)
    _file = syn.store(_file)
    _file2 = synapseclient.File(path=SAMPLE_FILE, name='file2.csv',
                                parent=project)
    _file2 = syn.store(_file2)
    _file3 = synapseclient.File(path=SAMPLE_FILE, name='file3.csv.gz',
                                parent=project)
    _file3 = syn.store(_file3)
    # store a sample metadata file
    meta = synapseclient.File(path=SAMPLE_META, name='meta', parent=project)
    meta = syn.store(meta)
    # store a sample table (same values as sample file)
    df = sampleEntities['data']
    cols = synapseclient.as_table_columns(df)
    schema = synapseclient.Schema(name=str(uuid.uuid4()), columns=cols,
                                  parent=project)
    schema = syn.store(schema)
    table = syn.store(synapseclient.Table(schema, df))
    # store a sample file view
    entity_view = _entity_view(syn, project)
    ents = {'files': [_file, _file2, _file3],
            'meta': meta,
            'schema': schema,
            'entity_view': entity_view}
    return ents
