"""daily60s 配置解析辅助"""

from __future__ import annotations

from dataclasses import dataclass

from .config import ApiName, Daily60sPluginConfig, PushType, ScheduleConfig, TargetFilterType, TriggerConfig


@dataclass(frozen=True)
class CommandMatch:
    """一次命令触发匹配结果"""

    api_name: ApiName
    push_type: PushType


@dataclass(frozen=True)
class ScheduleTask:
    """展开后的单个定时推送任务"""

    api_name: ApiName
    push_type: PushType
    push_time: str
    groups_type: TargetFilterType
    groups: tuple[str, ...]
    users_type: TargetFilterType
    users: tuple[str, ...]


def _dedupe_values(values: list[str]) -> list[str]:
    """保持顺序去重"""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _target_allowed(filter_type: TargetFilterType, targets: list[str], target_id: str) -> bool:
    """根据名单模式判断当前目标是否允许触发"""
    if not targets:
        return True
    if filter_type == "whitelist":
        return target_id in targets
    return target_id not in targets


def get_command_keywords(config: Daily60sPluginConfig, api_name: ApiName) -> list[str]:
    """获取 API 对应的命令关键词，默认命令为 /<api_name>"""
    aliases = getattr(config.command_alias_config, api_name)
    return _dedupe_values([f"/{api_name}", *aliases])


def find_command_match(
    config: Daily60sPluginConfig,
    command_token: str,
    target_kind: str,
    target_id: str,
) -> CommandMatch | None:
    """按命令触发配置匹配 API"""
    normalized_command = command_token.lower()
    for trigger_config in config.command_trigger_config.trigger_list:
        if not trigger_config.enabled:
            continue
        if not _trigger_allows_target(trigger_config, target_kind=target_kind, target_id=target_id):
            continue

        for api_name in trigger_config.apis:
            keywords = get_command_keywords(config, api_name)
            if any(normalized_command == keyword.lower() for keyword in keywords):
                return CommandMatch(api_name=api_name, push_type=trigger_config.push_type)
    return None


def iter_menu_api_names(config: Daily60sPluginConfig) -> list[ApiName]:
    """按命令触发配置顺序返回菜单中可展示的 API"""
    api_names: list[ApiName] = []
    seen: set[ApiName] = set()
    for trigger_config in config.command_trigger_config.trigger_list:
        if not trigger_config.enabled:
            continue
        for api_name in trigger_config.apis:
            if api_name in seen:
                continue
            seen.add(api_name)
            api_names.append(api_name)
    return api_names


def iter_schedule_tasks(config: Daily60sPluginConfig) -> list[ScheduleTask]:
    """将定时推送配置展开为单 API 任务"""
    tasks: list[ScheduleTask] = []
    for schedule_config in config.schedule_push_config.schedule_list:
        if not schedule_config.enabled:
            continue
        tasks.extend(_expand_schedule_config(schedule_config))
    return tasks


def _trigger_allows_target(trigger_config: TriggerConfig, target_kind: str, target_id: str) -> bool:
    if target_kind == "group":
        return _target_allowed(trigger_config.groups_type, trigger_config.groups, target_id)
    if target_kind == "user":
        return _target_allowed(trigger_config.users_type, trigger_config.users, target_id)
    return False


def _expand_schedule_config(schedule_config: ScheduleConfig) -> list[ScheduleTask]:
    return [
        ScheduleTask(
            api_name=api_name,
            push_type=schedule_config.push_type,
            push_time=schedule_config.push_time,
            groups_type=schedule_config.groups_type,
            groups=tuple(schedule_config.groups),
            users_type=schedule_config.users_type,
            users=tuple(schedule_config.users),
        )
        for api_name in schedule_config.apis
    ]
