import os
from enum import Enum

from trame import change, flush_state, update_state
from trame.layouts import SinglePageWithDrawer
from trame.html import vtk, vuetify, widgets

from vtkmodules.vtkCommonDataModel import (
    vtkDataObject,
)
from vtkmodules.vtkIOXML import (
    vtkXMLUnstructuredGridReader,
)
from vtkmodules.vtkRenderingAnnotation import (
    vtkCubeAxesActor,
)
from vtkmodules.vtkFiltersCore import (
    vtkContourFilter,
)
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkDataSetMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

# Required for interacter factory initialization
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleSwitch  # noqa

# Required for remote rendering factory initialization, not necessary for
# local rendering, but doesn't hurt to include it
import vtkmodules.vtkRenderingOpenGL2  # noqa

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------


class Representation(Enum):
    Points = 0
    Wireframe = 1
    Surface = 2
    SurfaceWithEdges = 3


REPRESENTATIONS = [
    {"text": "Points", "value": 0},
    {"text": "Wireframe", "value": 1},
    {"text": "Surface", "value": 2},
    {"text": "SurfaceWithEdges", "value": 3},
]


class LUT(Enum):
    Rainbow = 0
    Inverted_Rainbow = 1
    Greyscale = 2
    Inverted_Greyscale = 3


COLOR_MAPS = [
    {"text": "Rainbow", "value": 0},
    {"text": "Inv Rainbow", "value": 1},
    {"text": "Greyscale", "value": 2},
    {"text": "Inv Greyscale", "value": 3},
]

# -----------------------------------------------------------------------------
# VTK helpers
# -----------------------------------------------------------------------------


def create_representation(input):
    mapper = vtkDataSetMapper()
    mapper.SetInputConnection(input.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    return actor


def use_preset(actor, preset):
    lut = actor.GetMapper().GetLookupTable()
    lut_preset = LUT(preset)
    if lut_preset == LUT.Rainbow:
        lut.SetHueRange(0.666, 0.0)
        lut.SetSaturationRange(1.0, 1.0)
        lut.SetValueRange(1.0, 1.0)
    elif lut_preset == LUT.Inverted_Rainbow:
        lut.SetHueRange(0.0, 0.666)
        lut.SetSaturationRange(1.0, 1.0)
        lut.SetValueRange(1.0, 1.0)
    elif lut_preset == LUT.Greyscale:
        lut.SetHueRange(0.0, 0.0)
        lut.SetSaturationRange(0.0, 0.0)
        lut.SetValueRange(0.0, 1.0)
    elif lut_preset == LUT.Inverted_Greyscale:
        lut.SetHueRange(0.0, 0.666)
        lut.SetSaturationRange(0.0, 0.0)
        lut.SetValueRange(1.0, 0.0)
    lut.Build()


def color_by_array(actor, array):
    _min, _max = array.get("range")
    mapper = actor.GetMapper()
    mapper.GetLookupTable().SetRange(_min, _max)
    mapper.SelectColorArray(array.get("text"))
    mapper.SetScalarModeToUsePointFieldData()
    mapper.SetScalarVisibility(True)
    mapper.SetUseLookupTableScalarRange(True)


def update_representation(actor, mode):
    property = actor.GetProperty()
    rep = Representation(mode)
    if rep == Representation.Points:
        property.SetRepresentationToPoints()
        property.SetPointSize(5)
        property.EdgeVisibilityOff()
    elif rep == Representation.Wireframe:
        property.SetRepresentationToWireframe()
        property.SetPointSize(1)
        property.EdgeVisibilityOff()
    elif rep == Representation.Surface:
        property.SetRepresentationToSurface()
        property.SetPointSize(1)
        property.EdgeVisibilityOff()
    elif rep == Representation.SurfaceWithEdges:
        property.SetRepresentationToSurface()
        property.SetPointSize(1)
        property.EdgeVisibilityOn()


def contour_by_array(filter, array, reset_value=True):
    _min, _max = array.get("range")
    step = 0.01 * (_max - _min)
    value = 0.5 * (_max + _min)
    filter.SetInputArrayToProcess(0, 0, 0, array.get("type"), array.get("text"))
    if reset_value:
        filter.SetValue(0, value)
    return value, step


# -----------------------------------------------------------------------------
# VTK pipeline
# -----------------------------------------------------------------------------

renderer = vtkRenderer()
renderWindow = vtkRenderWindow()
renderWindow.AddRenderer(renderer)

renderWindowInteractor = vtkRenderWindowInteractor()
renderWindowInteractor.SetRenderWindow(renderWindow)
renderWindowInteractor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

reader = vtkXMLUnstructuredGridReader()
reader.SetFileName(os.path.join(CURRENT_DIRECTORY, "../data/disk_out_ref.vtu"))
reader.Update()
dataset = reader.GetOutput()

# Extract arrays informations
dataset_arrays = []
fields = [
    (dataset.GetPointData(), vtkDataObject.FIELD_ASSOCIATION_POINTS),
    (dataset.GetCellData(), vtkDataObject.FIELD_ASSOCIATION_CELLS),
]
for field in fields:
    field_arrays, association = field
    for i in range(field_arrays.GetNumberOfArrays()):
        array = field_arrays.GetArray(i)
        array_range = array.GetRange()
        dataset_arrays.append(
            {
                "text": array.GetName(),
                "value": i,
                "range": list(array_range),
                "type": association,
            }
        )
default_array = dataset_arrays[0]

# Mesh
mesh_actor = create_representation(reader)
update_representation(mesh_actor, Representation.Surface)
use_preset(mesh_actor, LUT.Rainbow)
color_by_array(mesh_actor, default_array)
renderer.AddActor(mesh_actor)

# Cube Axes
cube_axes = vtkCubeAxesActor()
cube_axes.SetBounds(mesh_actor.GetBounds())
cube_axes.SetCamera(renderer.GetActiveCamera())
cube_axes.SetXLabelFormat("%6.1f")
cube_axes.SetYLabelFormat("%6.1f")
cube_axes.SetZLabelFormat("%6.1f")
cube_axes.SetFlyModeToOuterEdges()
renderer.AddActor(cube_axes)

# Contour
contour_array = dataset_arrays[0]
contour = vtkContourFilter()
contour.SetInputConnection(reader.GetOutputPort())
contour_value, contour_step = contour_by_array(contour, contour_array)
contour_actor = create_representation(contour)
contour_min, contour_max = contour_array.get("range")
update_representation(contour_actor, Representation.Surface)
use_preset(contour_actor, LUT.Rainbow)
color_by_array(contour_actor, contour_array)
renderer.AddActor(contour_actor)

renderer.ResetCamera()

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

local_view = vtk.VtkLocalView(renderWindow)
remote_view = vtk.VtkRemoteView(renderWindow, interactive_ratio=(1,))
html_view = local_view


@change("cube_axes_visibility")
def update_cube_axes_visibility(cube_axes_visibility, **kwargs):
    cube_axes.SetVisibility(cube_axes_visibility)
    html_view.update()


@change("local_vs_remote")
def update_local_vs_remote(local_vs_remote, **kwargs):
    # Switch html_view
    global html_view
    if local_vs_remote:
        html_view = local_view
    else:
        html_view = remote_view

    # Update layout
    layout.content.children[0].children[0] = html_view
    layout.flush_content()

    # Update View data
    html_view.update()


@change("mesh_representation")
def update_mesh_representation(mesh_representation, **kwargs):
    update_representation(mesh_actor, mesh_representation)
    html_view.update()


@change("contour_representation")
def update_contour_representation(contour_representation, **kwargs):
    update_representation(contour_actor, contour_representation)
    html_view.update()


@change("mesh_color_array_idx")
def update_mesh_color_by_name(mesh_color_array_idx, **kwargs):
    array = dataset_arrays[mesh_color_array_idx]
    color_by_array(mesh_actor, array)
    html_view.update()


@change("contour_color_array_idx")
def update_contour_color_by_name(contour_color_array_idx, **kwargs):
    array = dataset_arrays[contour_color_array_idx]
    color_by_array(contour_actor, array)
    html_view.update()


@change("mesh_color_preset")
def update_mesh_color_preset(mesh_color_preset, **kwargs):
    use_preset(mesh_actor, mesh_color_preset)
    html_view.update()


@change("contour_color_preset")
def update_contour_color_preset(contour_color_preset, **kwargs):
    use_preset(contour_actor, contour_color_preset)
    html_view.update()


@change("mesh_opacity")
def update_mesh_opacity(mesh_opacity, **kwargs):
    mesh_actor.GetProperty().SetOpacity(mesh_opacity)
    html_view.update()


@change("contour_opacity")
def update_contour_opacity(contour_opacity, **kwargs):
    contour_actor.GetProperty().SetOpacity(contour_opacity)
    html_view.update()


@change("contour_by_array_idx")
def update_contour_by(contour_by_array_idx, **kwargs):
    array = dataset_arrays[contour_by_array_idx]
    contour_value, contour_step = contour_by_array(contour, array)
    contour_min, contour_max = array.get("range")

    update_state("contour_min", contour_min)
    update_state("contour_max", contour_max)
    update_state("contour_value", contour_value)
    update_state("contour_step", contour_step)

    html_view.update()


@change("contour_value")
def update_contour_value(contour_value, **kwargs):
    contour.SetValue(0, float(contour_value))
    html_view.update()


# Called by pipeline when selection change
def actives_change(ids):
    _id = ids[0]
    if _id == "1":  # Mesh
        update_state("active_ui", "mesh")
    elif _id == "2":  # Contour
        update_state("active_ui", "contour")
    else:
        update_state("active_ui", "nothing")


# Called by pipeline when visibility change
def visibility_change(event):
    _id = event["id"]
    _visibility = event["visible"]

    if _id == "1":  # Mesh
        mesh_actor.SetVisibility(_visibility)
    elif _id == "2":  # Contour
        contour_actor.SetVisibility(_visibility)

    html_view.update()


# -----------------------------------------------------------------------------
# GUI Cards
# -----------------------------------------------------------------------------

compact_style = {
    "hide_details": True,
    "dense": True,
}

select_style = {
    **compact_style,
    "outlined": True,
    "classes": "pt-1",
}


def ui_card(title, ui_name):
    with vuetify.VCard(v_show=f"active_ui == '{ui_name}'"):
        vuetify.VCardTitle(
            title,
            classes="grey lighten-1 py-1 grey--text text--darken-3",
            style="user-select: none; cursor: pointer",
            **compact_style,
        )
        content = vuetify.VCardText(classes="py-2")

    return content


def pipeline_browser():
    widgets.GitTree(
        sources=(
            "pipeline",
            [
                {"id": "1", "parent": "0", "visible": 1, "name": "Mesh"},
                {"id": "2", "parent": "1", "visible": 1, "name": "Contour"},
            ],
        ),
        actives_change=(actives_change, "[$event]"),
        visibility_change=(visibility_change, "[$event]"),
    )


def mesh_card():
    with ui_card("Mesh", "mesh"):
        vuetify.VSelect(
            v_model=("mesh_representation", Representation.Surface.value),
            items=("representations", REPRESENTATIONS),
            label="Representation",
            **select_style,
        )
        with vuetify.VRow(classes="pt-2", dense=True):
            with vuetify.VCol(cols="6"):
                vuetify.VSelect(
                    label="Color by",
                    v_model=("mesh_color_array_idx", 0),
                    items=("array_list", dataset_arrays),
                    **select_style,
                )
            with vuetify.VCol(cols="6"):
                vuetify.VSelect(
                    label="Colormap",
                    v_model=("mesh_color_preset", LUT.Rainbow.value),
                    items=("colormaps", COLOR_MAPS),
                    **select_style,
                )
        vuetify.VSlider(
            v_model=("mesh_opacity", 1.0),
            min=0,
            max=1,
            step=0.1,
            label="Opacity",
            classes="mt-1",
            **compact_style,
        )


def contour_card():
    with ui_card("Contour", "contour"):
        vuetify.VSelect(
            label="Contour by",
            v_model=("contour_by_array_idx", 0),
            items=("array_list", dataset_arrays),
            **select_style,
        )
        vuetify.VSlider(
            v_model=("contour_value", contour_value),
            min=("contour_min", contour_min),
            max=("contour_max", contour_max),
            step=("contour_step", contour_step),
            label="Value",
            classes="my-1",
            **compact_style,
        )
        vuetify.VSelect(
            v_model=("contour_representation", Representation.Surface.value),
            items=("representations", REPRESENTATIONS),
            label="Representation",
            **select_style,
        )
        with vuetify.VRow(classes="pt-2", dense=True):
            with vuetify.VCol(cols="6"):
                vuetify.VSelect(
                    label="Color by",
                    v_model=("contour_color_array_idx", 0),
                    items=("array_list", dataset_arrays),
                    **select_style,
                )
            with vuetify.VCol(cols="6"):
                vuetify.VSelect(
                    label="Colormap",
                    v_model=("contour_color_preset", LUT.Rainbow.value),
                    items=("colormaps", COLOR_MAPS),
                    **select_style,
                )
        vuetify.VSlider(
            v_model=("contour_opacity", 1.0),
            min=0,
            max=1,
            step=0.1,
            label="Opacity",
            classes="mt-1",
            **compact_style,
        )


# -----------------------------------------------------------------------------
# GUI
# -----------------------------------------------------------------------------

layout = SinglePageWithDrawer("Trame Viewer", on_ready=html_view.update)
layout.title.set_text("Viewer")

toggle_buttons = [
    (("cube_axes_visibility", True), "mdi-cube-outline", "mdi-cube-off-outline"),
    ("$vuetify.theme.dark", "mdi-lightbulb-off-outline", "mdi-lightbulb-outline"),
    (("local_vs_remote", True), "mdi-lan-disconnect", "mdi-lan-connect"),
]

with layout.toolbar:
    vuetify.VSpacer()
    vuetify.VDivider(vertical=True, classes="mx-2")
    for model, on, off in toggle_buttons:
        vuetify.VCheckbox(
            v_model=model,
            on_icon=on,
            off_icon=off,
            classes="mx-1",
            **compact_style,
        )
    with vuetify.VBtn(icon=True, click="$refs.view.resetCamera()"):
        vuetify.VIcon("mdi-crop-free")

with layout.drawer as drawer:
    drawer.width = 325
    pipeline_browser()
    vuetify.VDivider()
    mesh_card()
    contour_card()

with layout.content:
    vuetify.VContainer(
        fluid=True,
        classes="pa-0 fill-height",
        children=[html_view],
    )

# State use to track active ui card
layout.state = {
    "active_ui": None,
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    layout.start()
