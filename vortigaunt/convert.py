import FbxCommon
from fbx import (
    FbxDocumentInfo,
    FbxMesh,
    FbxNode,
    FbxVector4,
    FbxVector2,
    FbxAxisSystem,
    FbxLODGroup,
    FbxDistance,
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

    # begin convert
    for mdl_bp, vtx_bp in zip(mdl.bodyparts, vtx.body_parts):

        lod_group = FbxNode.Create(manager, mdl_bp.name)
        lod_group_attr = FbxLODGroup.Create(manager, '')
        lod_group.SetNodeAttribute(lod_group_attr)
        lod_thresholds = 0.0

        for lod_index in range(vtx.num_lods):
            for mdl_model, vtx_model in zip(mdl_bp.models, vtx_bp.models):
                # mdl_model_vnum = 0
                if mdl_model.num_meshes == 0:
                    continue
                vtx_model_lod = vtx_model.model_lods[lod_index]
                if vtx_model_lod.switch_point < 0.0:
                    continue
                if lod_index > 0:
                    lod_thresholds += vtx_model_lod.switch_point
                    lod_group_attr.AddThreshold(FbxDistance(lod_thresholds, ''))

                node_name = f"{mdl_bp.name}_lod{lod_index}"
                node = FbxNode.Create(manager, node_name)
                mesh = FbxMesh.Create(manager, '')

                # Create LayerElements
                smoothing = mesh.CreateElementSmoothing()
                smoothing.SetMappingMode(3)  # Polygon
                smoothing.SetReferenceMode(0)  # Direct
                smoothing_direct = smoothing.GetDirectArray()
                uv = mesh.CreateElementUV('')
                uv.SetMappingMode(2)  # PolygonVertex
                uv.SetReferenceMode(2)  # IndexToDirect
                uv_direct = uv.GetDirectArray()
                uv_index = uv.GetIndexArray()

                # Vertexes
                mesh.InitControlPoints(len(fixed_vertexes))
                for i in range(len(fixed_vertexes)):
                    vertex = fixed_vertexes[i]
                    mesh.SetControlPointAt(
                        FbxVector4(*vertex.position),
                        FbxVector4(*vertex.normal),
                        i,
                    )
                    tex_coord = vertex.tex_coord
                    uv_direct.Add(FbxVector2(tex_coord[0], -tex_coord[1]))
                node.SetNodeAttribute(mesh)
                for mdl_mesh, vtx_mesh in zip(mdl_model.meshes, vtx_model_lod.meshes):
                    for vtx_sg in vtx_mesh.strip_groups:
                        # Indices
                        for vtx_strip in vtx_sg.strips:
                            for i in range(vtx_strip.num_indices // 3):
                                for j in range(3):
                                    i1 = i*3 + [0, 2, 1][j] + vtx_strip.index_offset
                                    i2 = vtx_sg.indices[i1]
                                    vertex = vtx_sg.vertexes[i2]
                                    i3 = vertex.orig_mesh_vert_id
                                    i4 = mdl_mesh.vertex_offset + i3  # + mdl_model_vnum
                                    index = i4 + mdl_model.vertex_index / 48

                                    if j == 0:
                                        mesh.BeginPolygon()
                                    mesh.AddPolygon(index)
                                    if j == 2:
                                        mesh.EndPolygon()
                                        smoothing_direct.Add(1)
                                    uv_index.Add(i3)
                    # mdl_model_vnum += mdl_mesh.num_vertices
                lod_group.AddChild(node)
        root.AddChild(lod_group)

    fbx_name = mdl_name[:-4] + '.fbx'
    FbxCommon.SaveScene(manager, scene, fbx_name, pFileFormat=0)
    print(f'saved "{fbx_name}"')
