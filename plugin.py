def create_plugin():
    """创建每日信息速递插件实例。"""

    from .core.plugin import Daily60sPlugin

    return Daily60sPlugin()
