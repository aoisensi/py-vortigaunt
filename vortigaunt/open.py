from srcstudiomodel import MDL, VTX, VVD
from os.path import exists


def open_mdl(mdl_name: str) -> MDL:
    if not exists(mdl_name):
        raise Exception(f'{mdl_name} is not found')

    if not mdl_name.endswith('.mdl'):
        raise Exception('the filename is not end with ".mdl"')

    with open(mdl_name, 'rb') as mdlf:
        return MDL(mdlf)


def open_vtx(mdl_name: str) -> VTX:
    name = mdl_name[:-4] + '.dx90.vtx'
    if not exists(name):
        raise Exception(f'"{name}" is not found')

    with open(name, 'rb') as f:
        return VTX(f)


def open_vvd(mdl_name: str) -> VVD:
    name = mdl_name[:-4] + '.vvd'
    if not exists(name):
        raise Exception(f'"{name}" is not found')

    with open(name, 'rb') as f:
        return VVD(f)
