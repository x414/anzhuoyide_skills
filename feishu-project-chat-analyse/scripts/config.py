"""
飞书 Skill 统一配置管理
支持 config.yaml 和命令行参数覆盖

用法:
    from config import load_config, CONFIG

    # 加载配置
    load_config('./config.yaml')

    # 使用配置
    print(CONFIG['feishu']['tenant'])
    print(CONFIG['extraction']['scroll_duration'])
"""
import os
import json

# 默认配置
DEFAULT_CONFIG = {
    "feishu": {
        "tenant": "<tenant>.feishu.cn",
        "messenger_url": "https://<tenant>.feishu.cn/messenger",
        "cookies_path": "./feishu_analysis/data/feishu_cookies.json",
        "auto_detect_tenant": True,
    },
    "browser": {
        "headless": False,
        "viewport_width": 1920,
        "viewport_height": 1080,
        "args": ["--no-sandbox"],
        "auto_detect_chrome": True,
        "chrome_path": None,  # 设为非None则使用指定路径
    },
    "display": {
        "auto_set": True,
        "display": ":0",
        "xauthority_paths": [
            os.path.expanduser("~/.Xauthority"),
        ],
    },
    "extraction": {
        "scroll_duration": 1800,
        "scroll_step_min": 200,
        "scroll_step_max": 500,
        "pause_min": 1.5,
        "pause_max": 3.0,
        "max_rounds": 200,
        "no_growth_threshold": 10,
        "accumulate_mode": True,
        "output_format": "txt",  # txt | json | md
    },
    "incremental": {
        "enabled": True,
        "state_file": "./feishu_analysis/data/extraction_state.json",
        "skip_threshold_chars": 100,  # 消息内容重复多少字符视为已提取
    },
    "batch": {
        "max_workers": 2,
        "retry_count": 3,
        "retry_delay": 5,
        "report_file": "./feishu_analysis/reports/batch_extraction_report.json",
    },
    "output": {
        "dir": "./feishu_analysis/data",
        "reports_dir": "./feishu_analysis/reports",
        "logs_dir": "./feishu_analysis/logs",
    },
    "logging": {
        "level": "INFO",  # DEBUG | INFO | WARNING | ERROR
        "file": "./feishu_analysis/logs/feishu_skill.log",
        "format": "%(asctime)s [%(levelname)s] %(message)s",
    },
}

# 全局配置对象
CONFIG = dict(DEFAULT_CONFIG)


def load_config(config_path=None):
    """
    加载配置文件，支持 yaml 和 json 格式

    Args:
        config_path: 配置文件路径，None 则使用默认配置

    Returns:
        合并后的配置字典
    """
    global CONFIG

    # 重置为默认
    CONFIG = dict(DEFAULT_CONFIG)

    if config_path and os.path.exists(config_path):
        ext = os.path.splitext(config_path)[1].lower()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if ext in ('.yaml', '.yml'):
                    try:
                        import yaml
                        user_config = yaml.safe_load(f)
                    except ImportError:
                        print("[WARN] PyYAML not installed, falling back to JSON")
                        user_config = {}
                else:
                    user_config = json.load(f)

            # 深度合并
            _deep_merge(CONFIG, user_config)
            print(f"[INFO] Config loaded from {config_path}")
        except Exception as e:
            print(f"[WARN] Failed to load config from {config_path}: {e}")
            print("[INFO] Using default config")
    else:
        if config_path:
            print(f"[WARN] Config file not found: {config_path}")
        print("[INFO] Using default config")

    # 自动检测租户域名
    if CONFIG['feishu']['auto_detect_tenant']:
        _auto_detect_tenant()

    # 确保输出目录存在
    _ensure_dirs()

    return CONFIG


def _deep_merge(base, override):
    """深度合并两个字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _auto_detect_tenant():
    """从 cookies 文件中自动检测租户域名"""
    cookies_path = CONFIG['feishu']['cookies_path']
    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, 'r') as f:
                cookies = json.load(f)
            for c in cookies:
                domain = c.get('domain', '')
                if '.feishu.cn' in domain and domain != '.feishu.cn':
                    # 提取租户域名，如 <tenant>.feishu.cn
                    tenant = domain.lstrip('.')
                    CONFIG['feishu']['tenant'] = tenant
                    CONFIG['feishu']['messenger_url'] = f"https://{tenant}/messenger"
                    print(f"[INFO] Auto-detected tenant: {tenant}")
                    return
        except Exception:
            pass


def _ensure_dirs():
    """确保所有配置目录存在"""
    dirs_to_create = [
        CONFIG['output']['dir'],
        CONFIG['output']['reports_dir'],
        CONFIG['output']['logs_dir'],
    ]
    for d in dirs_to_create:
        os.makedirs(d, exist_ok=True)


def get(key_path, default=None):
    """
    通过点号路径获取配置值

    Args:
        key_path: 如 'feishu.tenant' 或 'extraction.scroll_duration'
        default: 默认值

    Returns:
        配置值或默认值
    """
    keys = key_path.split('.')
    value = CONFIG
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def setup_display():
    """
    根据配置设置 DISPLAY 环境变量
    所有脚本应在启动浏览器前调用此函数
    """
    if not CONFIG['display']['auto_set']:
        return

    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = CONFIG['display']['display']

    # 尝试找到 Xauthority
    for xauth_path in CONFIG['display']['xauthority_paths']:
        if os.path.exists(xauth_path):
            os.environ["XAUTHORITY"] = xauth_path
            break
    else:
        # 尝试自动发现
        import glob
        home = os.path.expanduser("~")
        patterns = [
            os.path.join(home, ".Xauthority"),
            "/run/user/*/.*Xwaylandauth*",
            "/tmp/.X11-unix/*",
        ]
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                os.environ["XAUTHORITY"] = matches[0]
                break


def setup_logging():
    """配置日志系统"""
    import logging

    log_config = CONFIG['logging']
    level = getattr(logging, log_config['level'].upper(), logging.INFO)

    # 创建日志目录
    log_file = log_config['file']
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 配置
    logging.basicConfig(
        level=level,
        format=log_config['format'],
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger('feishu_skill')


# 便捷属性访问
class ConfigProxy:
    """配置代理，支持 CONFIG.tenant 式访问"""
    def __getattr__(self, name):
        return get(name)


config_proxy = ConfigProxy()
