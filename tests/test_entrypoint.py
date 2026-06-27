from plugins.daily60s.plugin import create_plugin
from plugins.daily60s.core.plugin import Daily60sPlugin


def test_create_plugin_returns_core_plugin_instance():
    plugin = create_plugin()

    assert isinstance(plugin, Daily60sPlugin)


def test_root_plugin_module_only_exposes_entrypoint():
    import plugins.daily60s.plugin as entrypoint

    assert hasattr(entrypoint, "create_plugin")
    assert not hasattr(entrypoint, "Daily60sPlugin")
    assert "_Daily60sPlugin" not in vars(entrypoint)
