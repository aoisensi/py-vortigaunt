from typing import Optional, Tuple
from srcstudiomodel import MDL, VTX, VVD
from os.path import exists


def _open(mdl_name: str) -> Tuple[MDL, Optional[VTX], Optional[VVD]]:
    if not exists(mdl_name):
        raise Exception(f"{mdl_name} is not found")

    if not mdl_name.endswith(".mdl"):
        raise Exception('the filename is not end with ".mdl"')

    name = mdl_name[:-4]

    vtx_name = name + ".dx90.vtx"
    vvd_name = name + ".vvd"

    mdl = None
    with open(mdl_name, "rb") as mdlf:
        mdl = MDL(mdlf)

    vtx = None
    vvd = None

    if exists(vtx_name):
        with open(vtx_name, "rb") as vtxf:
            vtx = VTX(vtxf)
    if exists(vvd_name):
        with open(vvd_name, "rb") as vvdf:
            vvd = VVD(vvdf)

    return (mdl, vtx, vvd)
