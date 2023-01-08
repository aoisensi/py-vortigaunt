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
        axis = FbxAxisSystem(3, -2, 0)
        settings.SetAxisSystem(axis)
    set_global_settings()

    # begin convert
    vtx_mesh = vtx.body_parts[0].models[0].model_lods[0].meshes[0]
    vtx_sg = vtx_mesh.strip_groups[0]

    mdl_model = mdl.bodyparts[0].models[0]
    mdl_mesh = mdl_model.meshes[0]

    mesh = FbxMesh.Create(manager, mdl_model.name)

    # Vertexes Fixup
    def fixup():
        if vvd.fixups:
            fixed = []
            for fixup in vvd.fixups:
                # lod_index = 0
                # if fixup.lod >= lod_index:
                vid = fixup.source_vertex_id
                num = fixup.num_vertexes
                fixed += vvd.vertexes[vid:vid+num]
            return fixed
        else:
            return vvd.vertexes
    fixed_vertexes = fixup()

    # Vertexes
    mesh.InitControlPoints(len(fixed_vertexes))
    for i in range(len(fixed_vertexes)):
        vertex = fixed_vertexes[i]
        pos = vertex.position
        mesh.SetControlPointAt(FbxVector4(pos[0], pos[1], pos[2]), i)

    # Indices
    polygon_count = 0
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
                    polygon_count += 1

    # LayerElements
    # Smoothing
    smoothing = mesh.CreateElementSmoothing()
    smoothing.SetMappingMode(3)
    smoothing.SetReferenceMode(0)
    for _ in range(polygon_count):
        smoothing.GetDirectArray().Add(1)

    node = FbxNode.Create(manager, mdl_model.name)
    node.SetNodeAttribute(mesh)
    root.AddChild(node)

    fbx_name = mdl_name[:-4] + '.fbx'
    FbxCommon.SaveScene(manager, scene, fbx_name, pFileFormat=1)
    print(f'saved "{fbx_name}"')
