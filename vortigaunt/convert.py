import FbxCommon
from fbx import (
    FbxDocumentInfo,
    FbxMesh,
    FbxNode,
    FbxVector4,
    FbxAxisSystem,
)
from open import _open


def _transcoord():
    pass


def _convert(mdl_name: str):
    (mdl, vtx, vvd) = _open(mdl_name)
    (manager, scene) = FbxCommon.InitializeSdkObjects()

    # scene info
    scene_info = FbxDocumentInfo.Create(manager, 'SceneInfo')
    title = mdl.name
    if title.endswith('.mdl'):
        title = title[:-4]
    title = title.split('/')[-1]
    scene_info.mTitle = title
    scene_info.mAuthor = 'py-vortigaunt'
    scene.SetSceneInfo(scene_info)
    root = scene.GetRootNode()

    # global settings
    def set_global_settings():
        settings = scene.GetGlobalSettings()
        axis = FbxAxisSystem(2)
        settings.SetAxisSystem(axis)
    set_global_settings()
    # not working

    # begin convert
    vtx_mesh = vtx.body_parts[0].models[0].model_lods[0].meshes[0]
    vtx_sg = vtx_mesh.strip_groups[0]

    mesh = FbxMesh.Create(manager, '')
    mdl_model = mdl.bodyparts[0].models[0]
    mdl_mesh = mdl_model.meshes[0]
    # Vertexes
    mesh.InitControlPoints(len(vvd.vertexes))
    for i in range(len(vvd.vertexes)):
        vertex = vvd.vertexes[i]
        pos = vertex.position
        mesh.SetControlPointAt(FbxVector4(pos[0], pos[1], pos[2]), i)

    for vtx_strip in vtx_sg.strips:
        for i in range(vtx_strip.num_indices // 3):
            for j in range(3):
                i1 = i*3 + (2-j) + vtx_strip.index_offset
                i2 = vtx_sg.indices[i1]
                i3 = vtx_sg.vertexes[i2].orig_mesh_vert_id
                i4 = mdl_mesh.vertex_offset + i3
                index = i4 + mdl_model.vertex_index / 48

                if j == 0:
                    mesh.BeginPolygon(-1)
                mesh.AddPolygon(index)
                if j == 2:
                    mesh.EndPolygon()

    node = FbxNode.Create(manager, '')
    node.SetNodeAttribute(mesh)
    root.AddChild(node)

    FbxCommon.SaveScene(manager, scene, mdl_name[:-4], pFileFormat=1)
