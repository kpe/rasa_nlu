from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pytest
from rasa_nlu.model import Metadata

from rasa_nlu import registry
from rasa_nlu.components import fill_args, load_component, create_component, MissingArgumentError, \
    find_unavailable_packages, _read_dev_requirements
from rasa_nlu.extractors import EntityExtractor


@pytest.mark.parametrize("component_class", registry.component_classes)
def test_no_components_with_same_name(component_class):
    """The name of the components need to be unique as they will be referenced by name
    when defining processing pipelines."""

    names = [cls.name for cls in registry.component_classes]
    assert names.count(component_class.name) == 1, \
        "There is more than one component named {}".format(component_class.name)


@pytest.mark.parametrize("pipeline_template", registry.registered_pipeline_templates)
def test_all_components_in_model_templates_exist(pipeline_template):
    """We provide a couple of ready to use pipelines, this test ensures all components referenced by name in the
    pipeline definitions are available."""

    components = registry.registered_pipeline_templates[pipeline_template]
    for component in components:
        assert component in registry.registered_components, "Model template contains unknown component."


def test_all_components_are_in_all_components_template():
    """There is a template that includes all components to test the train-persist-load-use cycle. Ensures that really
    all Components are in there."""

    template_with_all_components = registry.registered_pipeline_templates["all_components"]
    for cls in registry.component_classes:
        assert cls.name in template_with_all_components, "`all_components` template is missing component."


@pytest.mark.parametrize("component_class", registry.component_classes)
def test_all_arguments_can_be_satisfied_during_init(component_class, default_config, component_builder):
    """Check that `pipeline_init` method parameters can be filled filled from the context.

    The parameters declared on the `pipeline_init` are not filled directly, rather the method is called via reflection.
    During the reflection, the parameters are filled from a so called context that is created when creating the
    pipeline and gets initialized with the configuration values. To make sure all arguments `pipeline_init` declares
    can be provided during the reflection, we do a 'dry run' where we check all parameters are part of the context."""

    # All available context arguments that will ever be generated during init
    component = component_builder.create_component(component_class.name, default_config)
    context_arguments = {}
    for clz in registry.component_classes:
        for ctx_arg in clz.context_provides.get("pipeline_init", []):
            context_arguments[ctx_arg] = None

    filled_args = fill_args(component.pipeline_init_args(), context_arguments, default_config.as_dict())
    assert len(filled_args) == len(component.pipeline_init_args())


@pytest.mark.parametrize("component_class", registry.component_classes)
def test_all_arguments_can_be_satisfied_during_train(component_class, default_config, component_builder):
    """Check that `train` method parameters can be filled filled from the context. Similar to `pipeline_init` test."""

    # All available context arguments that will ever be generated during train
    # it might still happen, that in a certain pipeline configuration arguments can not be satisfied!
    component = component_builder.create_component(component_class.name, default_config)
    context_arguments = {"training_data": None}
    for clz in registry.component_classes:
        for ctx_arg in clz.context_provides.get("pipeline_init", []):
            context_arguments[ctx_arg] = None
        for ctx_arg in clz.context_provides.get("train", []):
            context_arguments[ctx_arg] = None

    filled_args = fill_args(component.train_args(), context_arguments, default_config.as_dict())
    assert len(filled_args) == len(component.train_args())


@pytest.mark.parametrize("component_class", registry.component_classes)
def test_all_arguments_can_be_satisfied_during_parse(component_class, default_config, component_builder):
    """Check that `parse` method parameters can be filled filled from the context. Similar to `pipeline_init` test."""

    # All available context arguments that will ever be generated during parse
    component = component_builder.create_component(component_class.name, default_config)
    context_arguments = {"text": None}
    for clz in registry.component_classes:
        for ctx_arg in clz.context_provides.get("pipeline_init", []):
            context_arguments[ctx_arg] = None
        for ctx_arg in clz.context_provides.get("process", []):
            context_arguments[ctx_arg] = None

    filled_args = fill_args(component.process_args(), context_arguments, default_config.as_dict())
    assert len(filled_args) == len(component.process_args())


def test_all_extractors_use_previous_entities():
    extractors = [c for c in registry.component_classes if isinstance(c, EntityExtractor)]
    assert all(["entities" in ex.process_args() for ex in extractors])


def test_load_can_handle_none():
    assert load_component(None, {}, {}) is None


def test_create_can_handle_none():
    assert create_component(None, {}) is None


def test_fill_args_with_unsatisfiable_param_from_context():
    with pytest.raises(MissingArgumentError) as excinfo:
        fill_args(["good_one", "bad_one"], {"good_one": 1}, {})
    assert "bad_one" in str(excinfo.value)
    assert "good_one" not in str(excinfo.value)


def test_fill_args_with_unsatisfiable_param_from_config():
    with pytest.raises(MissingArgumentError) as excinfo:
        fill_args(["good_one", "bad_one"], {}, {"good_one": 1})
    assert "bad_one" in str(excinfo.value)
    assert "good_one" not in str(excinfo.value)


def test_find_unavailable_packages():
    unavailable = find_unavailable_packages(["my_made_up_package_name", "io", "foo_bar", "foo_bar"])
    assert unavailable == {"my_made_up_package_name", "foo_bar"}


def test_read_dev_requirements(tmpdir):
    package_name = "my_made_up_package_name"

    # two imaginary packages should be installed if imaginary `package_name` is required
    install_names = ["my_install_name_one", "my_install_name_two"]
    f = tmpdir.join("tmp-requirements.txt")
    f.write("# {}\n{}".format(package_name, "\n".join(install_names)))
    requirements = _read_dev_requirements(f.strpath)
    assert package_name in requirements
    assert requirements[package_name] == install_names


def test_builder_create_unknown(component_builder, default_config):
    with pytest.raises(Exception) as excinfo:
        component_builder.create_component("my_made_up_componment", default_config)
    assert "Unknown component name" in str(excinfo.value)


def test_builder_load_unknown(component_builder):
    with pytest.raises(Exception) as excinfo:
        component_builder.load_component("my_made_up_componment", {}, {}, Metadata({}, None))
    assert "Unknown component name" in str(excinfo.value)
