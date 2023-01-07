from typing import Tuple
from srcstudiomodel import MDL, VTX, VVD
from os.path import exists


def _open(mdl_name: str) -> Tuple[MDL, VTX, VVD]:
    if not exists(mdl_name):
        raise Exception(f"{mdl_name} is not found")

    if not mdl_name.endswith(".mdl"):
        raise Exception('the filename is not end with ".mdl"')

    name = mdl_name[:-4]

    vtx_name = name + ".dx90.vtx"
    vvd_name = name + ".vvd"

    if not exists(vtx_name):
        raise Exception(f"{vtx_name} is not found")
    if not exists(vvd_name):
        raise Exception(f"{vvd_name} is not found")

    with open(mdl_name, "rb") as mdlf:
        with open(vtx_name, "rb") as vtxf:
            with open(vvd_name, "rb") as vvdf:
                return (MDL(mdlf), VTX(vtxf), VVD(vvdf))
