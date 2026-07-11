#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Context Mining — 通用项目聊天记录深度上下文挖掘
支持21种项目类型：软件、硬件、设计、测试、管理、运营、销售、市场、售后、产品、算法、结构、供应链、质量、制造、产测、财务、IT、HR、法务、行政

Usage:
    python3 deep_context_mining.py \
        --input ./feishu_analysis/data/chat.txt \
        --output ./feishu_analysis/reports/report.md \
        --project-name "项目名称"
"""
import argparse, re, os
from collections import Counter, defaultdict

def dedup_lines(text):
    """Remove duplicate lines while preserving order."""
    seen = set()
    result = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped == '=== ROUND SEPARATOR ===':
            continue
        normalized = re.sub(r'\s+', ' ', stripped).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(stripped)
    return '\n'.join(result)



# ============ 项目类型定义 ============
PROJECT_TYPES = {
    'software': {
        'name': '软件/互联网',
        'keywords': ['代码', 'code', '软件', 'software', 'bug', 'feature', 'PR', 'merge', 'commit', 'repo', 'API', 'backend', 'frontend', '部署', 'release', 'version', '迭代', 'sprint', 'agile', '微服务', '数据库', '缓存', 'CDN', '容器', 'k8s', 'docker', 'CI/CD', 'git', 'branch', 'tag'],
        'role_hints': {'PM': ['PM', '项目经理', '产品经理', 'PD', 'owner', 'scrum master'], '研发': ['研发', '开发', '工程师', 'RD', '程序员', '架构师', '后端', '前端', '全栈', 'DevOps'], '测试': ['测试', 'QA', '质量', '自动化测试'], '设计': ['设计', 'UI', 'UX', '交互'], '运维': ['运维', 'SRE', '运维工程师'], '数据': ['数据', '算法', '模型', 'AI']},
        'asset_keywords': ['文件', 'function', 'module', 'class', 'service', 'API endpoint', '配置', '数据库表', 'commit', 'PR', 'branch'],
        'metric_keywords': ['bug', 'crash', 'latency', 'QPS', '吞吐量', '覆盖率', '成功率', '错误率', '耗时', '性能'],
    },
    'hardware': {
        'name': '硬件/嵌入式',
        'keywords': ['固件', 'firmware', '硬件', '物料', 'BOM', '试产', '产线', '供应商', '开模', '结构件', 'PCB', '组装', 'IQC', 'EVT', 'DVT', 'PVT', 'MP', '芯片', 'SoC', '电路', '射频', '天线', '模组', '传感器', '电池', '屏幕', '摄像头'],
        'role_hints': {'PM': ['PM', '项目经理', '产品经理'], '研发': ['研发', '固件', '驱动', '硬件工程师', '嵌入式', 'FPGA', 'RF'], '测试': ['测试', 'QA', '验证', '可靠性'], '结构': ['结构', '机械', 'ID', '外观', '模具'], '供应链': ['供应链', '采购', '物料', '供应商', 'sourcing'], '生产': ['生产', '制造', '工艺', 'NPI', '产线']},
        'asset_keywords': ['固件版本', 'BOM', '物料', '供应商', '测试站', '产线', 'PCB', '原理图', '结构件', '模具'],
        'metric_keywords': ['FR', '良率', '合格率', '不良率', '直通率', 'fail', 'pass', '温漂', '功耗', '信噪比'],
    },
    'design': {
        'name': '设计/创意',
        'keywords': ['设计', 'design', 'UI', 'UX', '视觉', '交互', '原型', 'Figma', 'Sketch', 'PS', 'AI', '品牌', '配色', '排版', '字体', 'icon', '动效', '创意', '文案', '海报', '视频', '拍摄', '剪辑'],
        'role_hints': {'设计总监': ['设计总监', '创意总监', '艺术总监'], '视觉设计': ['视觉', 'UI', 'GUI', '平面'], '交互设计': ['交互', 'UX', '体验'], '品牌设计': ['品牌', 'VI', 'logo'], '插画/动效': ['插画', '动效', '动画', '3D'], '文案策划': ['文案', '策划', '内容']},
        'asset_keywords': ['设计稿', '源文件', '素材', '字体', '图片', '视频', '原型', '组件库', '规范', 'guideline'],
        'metric_keywords': ['点击率', '转化率', '满意度', '审美', '曝光', '完播率', '留存'],
    },
    'testing': {
        'name': '测试/质量',
        'keywords': ['测试', 'test', 'QA', '用例', 'case', '自动化', '回归', '覆盖率', '缺陷', 'bug', '验证', '验收', '准入', '准出', 'test plan', 'test report', 'UT', 'IT', 'ST', 'UAT'],
        'role_hints': {'测试负责人': ['测试负责人', 'QA lead', '质量负责人'], '测试开发': ['测试开发', '自动化', '工具'], '功能测试': ['功能测试', '手工测试'], '性能测试': ['性能', '压测', 'load test'], '安全测试': ['安全', '渗透', '漏洞']},
        'asset_keywords': ['用例', 'case', '测试计划', '测试报告', '缺陷', 'bug', '测试数据', '环境', '工具'],
        'metric_keywords': ['覆盖率', '通过率', '缺陷密度', '漏测率', '回归率', 'MTBF', 'MTTR'],
    },
    'management': {
        'name': '项目管理',
        'keywords': ['项目', 'project', '里程碑', 'milestone', '甘特图', 'WBS', '风险', '干系人', '范围', '进度', '成本', '资源', '排期', '基线', '变更', '评审', '汇报', '立项', '结项', 'PMO'],
        'role_hints': {'PMO': ['PMO', '项目管理办公室'], '项目经理': ['项目经理', 'PM', '负责人'], '项目助理': ['项目助理', '助理'], 'Scrum Master': ['scrum master', '敏捷教练'], '高层': ['总监', 'VP', 'CTO', 'CEO']},
        'asset_keywords': ['项目计划', 'WBS', '风险登记册', '会议纪要', '决策记录', '变更单', '状态报告'],
        'metric_keywords': ['进度偏差', '成本偏差', '风险数量', '变更次数', '交付及时率', '满意度'],
    },
    'operations': {
        'name': '运营/服务',
        'keywords': ['运营', 'operations', '活动', '投放', '转化', '用户', 'DAU', 'MAU', '留存', '活跃', '拉新', '促活', '变现', 'ROI', 'GMV', '客单价', '复购', '漏斗', '渠道', '内容', '社群', '私域'],
        'role_hints': {'运营总监': ['运营总监', 'COO'], '用户运营': ['用户运营', '增长', '留存'], '内容运营': ['内容', '新媒体', '文案'], '活动运营': ['活动', '策划'], '数据运营': ['数据', '分析', 'BI'], '客服': ['客服', '售后', '支持']},
        'asset_keywords': ['活动方案', '投放计划', '数据报表', 'SOP', '话术', '素材', '渠道', '社群'],
        'metric_keywords': ['DAU', 'MAU', '留存', '转化率', 'ROI', 'GMV', '客单价', 'LTV', 'CAC', '漏斗'],
    },
    'sales': {
        'name': '销售/商务',
        'keywords': ['销售', 'sales', '客户', '商机', 'pipeline', '报价', '合同', '回款', '签单', '拜访', 'BD', '渠道', '代理', '分销', '大客户', 'KA', '直销', '电销', '客情', '赢单', '丢单'],
        'role_hints': {'销售总监': ['销售总监', 'VP销售', 'CMO'], '大客户经理': ['大客户', 'KA', '客户经理'], '销售代表': ['销售', 'BD', '商务'], '售前': ['售前', '解决方案', '顾问'], '渠道': ['渠道', '代理', '分销']},
        'asset_keywords': ['合同', '报价单', '标书', '方案', '客户档案', 'CRM', 'pipeline', '商机'],
        'metric_keywords': ['销售额', '签单额', '回款', '赢单率', '客单价', 'pipeline', '转化率', '拜访量'],
    },
    'marketing': {
        'name': '市场/品牌',
        'keywords': ['市场', 'marketing', '品牌', 'brand', '投放', '广告', 'PR', '公关', '展会', '活动', '舆情', 'SEO', 'SEM', '社交媒体', 'KOL', 'KOC', '内容营销', '种草', '曝光', '声量', '认知'],
        'role_hints': {'市场总监': ['市场总监', 'CMO', '品牌总监'], '品牌经理': ['品牌', 'PR', '公关'], '数字营销': ['数字营销', '投放', 'SEM', 'SEO'], '内容营销': ['内容', '新媒体', '社媒'], '活动市场': ['活动', '展会', '峰会']},
        'asset_keywords': ['品牌手册', 'VI', '素材', '广告创意', '新闻稿', '白皮书', '案例', '官网'],
        'metric_keywords': ['曝光', '点击', '转化', 'ROI', '声量', '认知度', 'NPS', '线索', 'MQL', 'SQL'],
    },
    'after_sales': {
        'name': '售后/客户成功',
        'keywords': ['售后', '支持', 'support', '客服', '投诉', '维修', '退换', '工单', 'ticket', 'SLA', '满意度', 'NPS', '客户成功', 'CSM', 'onboarding', '续约', '流失', '客诉', 'FAQ', '知识库'],
        'role_hints': {'售后总监': ['售后总监', '服务总监'], '客服': ['客服', '热线', '在线客服'], '技术支持': ['技术支持', '售后工程师', 'FAE'], '客户成功': ['客户成功', 'CSM'], '维修': ['维修', '返修', '备件']},
        'asset_keywords': ['工单', 'ticket', 'FAQ', '知识库', 'SOP', '备件', '维修手册', '服务合同'],
        'metric_keywords': ['满意度', 'NPS', 'SLA', '首次响应', '解决时长', '投诉率', '续约率', '流失率'],
    },
    'product': {
        'name': '产品管理',
        'keywords': ['产品', 'product', '需求', 'PRD', '用户故事', 'story', 'roadmap', 'feature', '功能', '优先级', ' backlog', '竞品', '用户调研', 'AB测试', 'MVP', '版本规划', '迭代', 'release note'],
        'role_hints': {'产品总监': ['产品总监', 'CPO'], '产品经理': ['产品经理', 'PM', 'PD'], '产品运营': ['产品运营', '增长产品'], '用户研究': ['用户研究', '用研', 'UXR'], '数据产品': ['数据产品', 'BI产品']},
        'asset_keywords': ['PRD', '原型', 'roadmap', 'backlog', '竞品分析', '用户画像', '数据报表', '需求池'],
        'metric_keywords': ['DAU', '留存', '转化率', '功能使用率', 'NPS', '需求交付率', '迭代周期'],
    },
    'algorithm': {
        'name': '算法/AI',
        'keywords': ['算法', 'algorithm', '模型', 'model', '训练', 'inference', '推理', '深度学习', '机器学习', 'NLP', 'CV', '推荐', '搜索', '排序', '特征', '数据集', '标注', '评测', 'AUC', 'F1', '准确率', '召回率'],
        'role_hints': {'算法负责人': ['算法负责人', '算法总监', '科学家'], '算法工程师': ['算法', '模型', '深度学习', '机器学习'], '数据工程师': ['数据工程', 'ETL', '特征工程'], '标注/评测': ['标注', '评测', '质检'], '应用产品': ['AI产品', '算法产品']},
        'asset_keywords': ['模型', 'checkpoint', '数据集', '特征表', '算法文档', '论文', '实验记录', 'baseline'],
        'metric_keywords': ['准确率', '召回率', 'F1', 'AUC', 'MAP', 'NDCG', '延迟', '吞吐', '资源占用'],
    },
    'structural': {
        'name': '结构/机械',
        'keywords': ['结构', '机械', 'CAD', 'ID', '外观', '模具', '注塑', '冲压', 'CNC', '钣金', '公差', '材料', '强度', '刚度', '疲劳', '振动', '热仿真', '流体', '装配', 'BOM', 'DFM', '公差分析'],
        'role_hints': {'结构总监': ['结构总监', '机械总监'], '结构工程师': ['结构', '机械', 'CAD'], 'ID设计': ['ID', '工业设计', '外观'], '模具工程师': ['模具', '注塑', '压铸'], '材料工程师': ['材料', '工艺', '表面处理']},
        'asset_keywords': ['CAD', '图纸', 'BOM', '模具', '治具', '检具', '仿真报告', '材料规格', 'DFM报告'],
        'metric_keywords': ['强度', '刚度', '公差', 'CPK', '良率', '寿命', '振动', '温升', '跌落'],
    },
    'supply_chain': {
        'name': '供应链/采购',
        'keywords': ['供应链', '采购', 'sourcing', '供应商', 'vendor', '库存', '仓储', '物流', '报关', '清关', '成本', '议价', '招标', '投标', '合同', '交付', '齐套', 'VMI', 'JIT', '呆滞', '周转'],
        'role_hints': {'供应链总监': ['供应链总监', '采购总监'], '采购': ['采购', 'sourcing', ' buyer'], '物流': ['物流', '仓储', '关务'], '计划': ['计划', '物控', 'PMC'], '质量': ['来料质量', 'SQE']},
        'asset_keywords': ['采购合同', '供应商档案', '库存报表', '物流单', '报关单', '成本分析', '询价单'],
        'metric_keywords': ['库存周转', '交付及时率', '成本降幅', '供应商合格率', '呆滞率', '缺料率'],
    },
    'quality': {
        'name': '质量管理',
        'keywords': ['质量', 'quality', 'ISO', '审核', 'audit', '内审', '外审', '不合格', 'NCR', 'CAPA', '8D', '5Why', 'FMEA', 'SPC', 'MSA', 'PPAP', 'APQP', '六西格玛', '精益', '持续改善', '客诉'],
        'role_hints': {'质量总监': ['质量总监', 'QA总监'], '体系工程师': ['体系', 'ISO', '审核'], '供应商质量': ['SQE', '供应商质量'], '过程质量': ['PQE', '过程质量'], '客户质量': ['CQE', '客诉', '售后质量']},
        'asset_keywords': ['质量手册', '程序文件', '检验标准', '8D报告', 'FMEA', '控制计划', '审核报告'],
        'metric_keywords': ['一次合格率', '客诉率', '审核不符合项', 'CAPA关闭率', '质量成本', 'PPM'],
    },
    'manufacturing': {
        'name': '生产制造',
        'keywords': ['生产', '制造', '产线', '工单', 'MO', '产能', 'OEE', 'TPM', '换线', '排产', 'MES', 'SOP', '作业指导书', '工时', '标准工时', '效率', '良率', '报废', '返工', '产能爬坡', '爬坡'],
        'role_hints': {'生产经理': ['生产经理', '制造经理', '厂长'], '工艺': ['工艺', 'PE', '制程'], '设备': ['设备', '维护', 'TPM'], '计划': ['生产计划', '排产', 'PMC'], '操作工': ['班组长', '线长', '操作工']},
        'asset_keywords': ['SOP', '作业指导书', 'MES', '工单', 'BOM', '工艺路线', '设备台账', '产能表'],
        'metric_keywords': ['OEE', '产能', '良率', '效率', '报废率', '返工率', '工时', 'UPH', 'MTBF'],
    },
    'production_testing': {
        'name': '生产测试',
        'keywords': ['产测', 'ATE', '测试治具', 'fixture', '测试程序', 'test program', '测试覆盖率', '功能测试', '老化', 'burn-in', 'HALT', 'HASS', 'ORT', '可靠性', '筛选', '抽检', '全检', 'FQC', 'OQC'],
        'role_hints': {'测试主管': ['测试主管', 'ATE主管'], '测试工程师': ['测试工程师', 'ATE', '产测'], '治具开发': ['治具', 'fixture', '夹具'], '可靠性': ['可靠性', 'HALT', '老化']},
        'asset_keywords': ['测试程序', '治具', '测试规范', '覆盖率报告', '可靠性报告', '筛选方案'],
        'metric_keywords': ['测试覆盖率', '误测率', '直通率', '筛选通过率', 'MTBF', '失效率'],
    },
    'finance': {
        'name': '财务/会计',
        'keywords': ['财务', 'finance', '会计', '预算', 'budget', '成本', '费用', '报销', '发票', '税务', '审计', '报表', '利润', '现金流', '固定资产', '折旧', '摊销', '融资', '投资', 'ROI', 'NPV'],
        'role_hints': {'财务总监': ['财务总监', 'CFO'], '会计': ['会计', '出纳', '应收', '应付'], '财务分析': ['财务分析', 'FP&A', '预算'], '税务': ['税务', '审计', '合规'], '成本': ['成本', '核算', '报价']},
        'asset_keywords': ['财务报表', '预算表', '科目表', '合同', '发票', '审计报告', '税务申报'],
        'metric_keywords': ['收入', '利润', '现金流', '预算执行率', '成本率', 'ROI', '周转率', '负债率'],
    },
    'it': {
        'name': 'IT/信息化',
        'keywords': ['IT', '系统', '信息化', '数字化', '网络', '安全', '服务器', '数据库', 'ERP', 'OA', 'CRM', 'HRIS', 'MES', 'WMS', '运维', 'helpdesk', 'ticket', 'SLA', '备份', '灾备', '渗透', '等保'],
        'role_hints': {'IT总监': ['IT总监', 'CIO', 'CTO'], '系统管理员': ['系统', '管理员', '运维'], '开发': ['开发', '二次开发', '接口'], '安全': ['安全', '等保', '渗透'], '桌面支持': ['桌面', 'helpdesk', '技术支持']},
        'asset_keywords': ['系统文档', '网络拓扑', '配置手册', 'SLA', '变更单', '故障记录', '资产台账'],
        'metric_keywords': ['系统可用性', '故障率', '响应时间', '解决时间', '变更成功率', '安全事件'],
    },
    'hr': {
        'name': '人力资源',
        'keywords': ['HR', '人力', '招聘', '面试', '绩效', '薪酬', '福利', '培训', '员工关系', '劳动法', '离职', '入职', '转正', '晋升', '调岗', '背调', 'offer', 'headcount', '编制', '组织架构', 'OD', 'TD', 'LD'],
        'role_hints': {'HRD': ['HRD', '人力总监', 'CHRO'], '招聘': ['招聘', '猎头', '校招'], '薪酬': ['薪酬', 'C&B', '福利'], '绩效': ['绩效', '考核', 'OKR'], '培训': ['培训', 'LD', 'TD'], '员工关系': ['员工关系', 'ER', '劳动法']},
        'asset_keywords': ['组织架构', '岗位说明书', '薪酬表', '绩效表', '培训计划', '员工手册', '劳动合同'],
        'metric_keywords': ['离职率', '入职率', '招聘周期', '人均产出', '培训覆盖率', '满意度', '敬业度'],
    },
    'legal': {
        'name': '法务/合规',
        'keywords': ['法务', 'legal', '合同', '协议', '知识产权', '专利', '商标', '版权', '诉讼', '仲裁', '合规', '监管', '政策', '法律风险', '尽职调查', 'NDA', '保密', '竞业', '劳动纠纷', '数据合规', '隐私'],
        'role_hints': {'法务总监': ['法务总监', '总法律顾问'], '合同': ['合同', '协议', '审核'], '知识产权': ['知识产权', '专利', '商标', 'IP'], '合规': ['合规', '监管', '政策'], '诉讼': ['诉讼', '仲裁', '争议']},
        'asset_keywords': ['合同', '协议', '专利文件', '商标注册', '法律意见书', '合规手册', '诉讼材料'],
        'metric_keywords': ['合同审核周期', '诉讼胜率', '知识产权数量', '合规事件', '法律风险等级'],
    },
    'admin': {
        'name': '行政/后勤',
        'keywords': ['行政', 'admin', '后勤', '办公', '物业', '车辆', '食堂', '宿舍', '采购', '固定资产', '办公用品', '会议', '接待', '差旅', '签证', '证照', '印章', '档案', '工会', '企业文化', '活动'],
        'role_hints': {'行政总监': ['行政总监', '行政经理'], '前台': ['前台', '接待'], '后勤': ['后勤', '物业', '司机'], '采购': ['采购', '行政采购'], '活动': ['活动', '企业文化', '工会']},
        'asset_keywords': ['固定资产台账', '办公用品清单', '会议记录', '档案', '证照', '印章台账', '采购合同'],
        'metric_keywords': ['费用预算执行率', '固定资产利用率', '员工满意度', '服务响应时间'],
    },
}

def detect_project_type(text):
    """基于关键词频率检测项目类型（支持混合）"""
    scores = {}
    for key, config in PROJECT_TYPES.items():
        score = sum(text.count(kw) for kw in config['keywords'])
        scores[key] = score
    
    # 排序取前3
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    primary = sorted_scores[0]
    secondary = sorted_scores[1] if len(sorted_scores) > 1 and sorted_scores[1][1] > 0 else None
    
    if primary[1] == 0:
        return 'generic', '通用项目'
    
    primary_name = PROJECT_TYPES[primary[0]]['name']
    if secondary and secondary[1] > primary[1] * 0.3:
        secondary_name = PROJECT_TYPES[secondary[0]]['name']
        return f"{primary[0]}+{secondary[0]}", f"{primary_name}+{secondary_name}"
    return primary[0], primary_name

def get_role_hints(project_type_key):
    """获取角色推断关键词"""
    if '+' in project_type_key:
        keys = project_type_key.split('+')
    else:
        keys = [project_type_key]
    
    merged = {}
    for k in keys:
        if k in PROJECT_TYPES:
            merged.update(PROJECT_TYPES[k]['role_hints'])
    return merged if merged else PROJECT_TYPES['software']['role_hints']

def is_person_name(name):
    """启发式判断字符串是否像人名"""
    if len(name) < 2 or len(name) > 25:
        return False
    non_name_keywords = ['All', '物料', '状态', '进度', '更新', '同步', '请查收', '请帮忙',
                         '确认', '沟通', '协调', '讨论', '会议', '今天', '明天', '后天',
                         '还未', '已经', '目前', '之前', '最近', '马上', '尽快',
                         '大家', '各位', '各位同事', '全体成员', '收到', '了解', '同意',
                         '所有人', '新人', '相关方', '负责人', '项目经理', '产品经理',
                         'Owner', 'owner', '全体成员', '全体成员']
    if any(kw in name for kw in non_name_keywords):
        return False
    if ' ' in name and len(name) > 18:
        return False
    # 排除纯中文长句（超过8个中文字符且没有英文名的）
    if len(name) > 12 and not re.search(r'[A-Za-z]', name):
        return False
    # 排除以"及"结尾的（如"项目经理及相关方"）
    if name.endswith('及') or name.endswith('和') or name.endswith('等'):
        return False
    return True

def infer_roles(text, lines, role_hints):
    """基于@mention和上下文推断角色"""
    mentions = re.findall(r'@([A-Za-z一-龥]+(?:\s+[A-Za-z一-龥]+)?)', text)
    mention_counter = Counter(mentions)
    top_people = [(p, c) for p, c in mention_counter.most_common(40) if is_person_name(p)]
    
    person_keywords = defaultdict(Counter)
    for line in lines:
        for person, _ in top_people:
            if person in line:
                for role_cat, kws in role_hints.items():
                    for kw in kws:
                        if kw in line:
                            person_keywords[person][role_cat] += 1
    
    role_map = {}
    for person, count in top_people:
        kws = person_keywords[person]
        if kws:
            best_role = kws.most_common(1)[0][0]
            role_map[person] = best_role
        else:
            role_map[person] = '核心成员'
    
    return role_map, mention_counter

def extract_version_issues(lines, project_type_key):
    """提取版本/发布问题"""
    version_issues = []
    version_patterns = [
        re.compile(r'(\d{2}\.\d\.\d{2}\.\d{3}(?:_[A-Z]+)?)'),
        re.compile(r'v?(\d+\.\d+\.\d+(?:[-_.]\w+)?)'),
        re.compile(r'(\d{4}\.\d{2}\.\d{2})'),
    ]
    fail_keywords = ['fail', '失败', 'bug', '问题', '异常', '回退', 'rollback', '回滚', '故障', '缺陷', '报错']
    
    for i, line in enumerate(lines):
        if any(k in line for k in ['版本', '发布', 'release', '上线', '固件', 'firmware', '更新', '部署']) and \
           any(k in line.lower() for k in fail_keywords):
            if 'Group announcement' in line or '日会原则' in line or len(line) > 350:
                continue
            date = None
            for j in range(max(0, i-3), i+1):
                dm = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}', lines[j])
                if dm:
                    date = dm.group(0)
                    break
            version = '未知'
            for pat in version_patterns:
                m = pat.search(line)
                if m:
                    version = m.group(1)
                    break
            resolved = any(k in line for k in ['PASS', 'pass', '正常', '已解决', 'OK', 'fixed', '修复', '恢复'])
            version_issues.append({'date': date or '未知', 'version': version, 'issue': line[:150], 'resolved': resolved})
    # dedup by issue text
    seen = set()
    unique = []
    for v in version_issues:
        key = v["issue"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique

def extract_quantity_evolution(lines):
    """提取数量/规模变化"""
    qty_lines = []
    change_keywords = ['减少', '增加', '缩减', '扩大到', '调整为', '变为', '砍', '扩', '由', '到', '调整']
    for i, line in enumerate(lines):
        has_change = any(k in line for k in change_keywords)
        has_number = re.search(r'\d+\s*(?:台|套|个|件|人|万|亿|条|份|张|页|次|天|小时|分钟)', line)
        if has_change and has_number:
            date = None
            for j in range(max(0, i-3), i+1):
                dm = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}', lines[j])
                if dm:
                    date = dm.group(0)
                    break
            qty_lines.append((date or '未知', line[:120]))
    qty_lines = list(dict.fromkeys(qty_lines))
    return qty_lines

def extract_external_dependencies(lines, project_type_key):
    """提取外部依赖"""
    deps = []
    dep_keywords = ['供应商', 'Vendor', '第三方', '外包', '合作方', '依赖', '外部', '采购', '合同', '客户', '甲方', '乙方']
    if '+' in project_type_key:
        keys = project_type_key.split('+')
    else:
        keys = [project_type_key]
    for k in keys:
        if k in PROJECT_TYPES:
            dep_keywords.extend(PROJECT_TYPES[k].get('asset_keywords', [])[:5])
    
    for line in lines:
        if any(k in line for k in dep_keywords) and len(line) > 20:
            deps.append(line[:150])
    return deps

def extract_cross_project_signals(lines):
    """提取跨项目/团队信号"""
    signals = []
    for line in lines:
        if any(k in line for k in ['其他项目', '别的项目', '兄弟项目', '共享', '借调', '协调', '优先级', '资源竞争', '抢', '冲突']):
            if len(line) > 20:
                signals.append(line[:150])
        elif '项目' in line and any(k in line for k in ['冲突', '竞争', '人力', '排期', '抢', '争']):
            if len(line) > 20:
                signals.append(line[:150])
    return signals

def extract_action_items(lines):
    """提取行动项"""
    items = []
    action_keywords = ['请', '需要', '要求', '务必', '必须', '帮忙', '协助', '跟进', '处理', '确认', '输出', '提交', 'review', '审批', '核对', '落实']
    for line in lines:
        if any(k in line for k in action_keywords) and '@' in line and len(line) > 30:
            items.append(line[:120])
    return items

def extract_quality_metrics(lines, project_type_key):
    """提取质量/性能指标"""
    metrics = []
    metric_keywords = ['FR:', 'fail', 'pass', '良率', '合格率', '不良率', '通过率', 'bug', '缺陷', '异常', '成功率', '覆盖率', '延迟', '耗时', 'error', 'crash', '准确率', '召回率', 'F1', 'AUC', 'DAU', '留存', '转化', 'ROI', 'GMV']
    if '+' in project_type_key:
        keys = project_type_key.split('+')
    else:
        keys = [project_type_key]
    for k in keys:
        if k in PROJECT_TYPES:
            metric_keywords.extend(PROJECT_TYPES[k].get('metric_keywords', [])[:5])
    
    for line in lines:
        if any(k in line for k in metric_keywords):
            metrics.append(line[:120])
    return metrics

def extract_risks(lines):
    """提取风险"""
    risks = []
    risk_keywords = ['风险', '延期', 'delay', '瓶颈', 'Hold', '暂停', 'block', '阻塞', '来不及', '天窗', '赶不上', '超标', 'delay', '逾期', '违约', '亏损', '投诉', '客诉']
    for line in lines:
        if any(k in line for k in risk_keywords) and len(line) > 15:
            risks.append(line[:150])
    return risks

def extract_governance(lines):
    """提取治理机制"""
    governance = []
    gov_keywords = ['公告', '制度', '纪律', '要求', '原则', '机制', '规范', '流程', '日会', '周报', '日报', '例会', '评审', '章程', 'standup', 'retro']
    for i, line in enumerate(lines):
        if any(k in line for k in gov_keywords):
            context = '\n'.join(lines[i:min(i+8, len(lines))])
            governance.append(context[:400])
    seen = set()
    unique = []
    for g in governance:
        key = re.sub(r'\s+', ' ', g[:80]).strip()
        if key not in seen:
            seen.add(key)
            unique.append(g)
    return unique[:5]

def extract_dates(text):
    """提取日期并推断年份，返回格式化的日期范围字符串"""
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    # 提取所有月日
    dates_found = re.findall(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})', text)
    
    # 尝试从文本中提取年份线索
    years = re.findall(r'(20\d{2})', text)
    year_counter = {}
    for y in years:
        year_counter[y] = year_counter.get(y, 0) + 1
    
    # 优先使用出现频率最高的年份，否则使用当前年份
    if year_counter:
        inferred_year = sorted(year_counter.items(), key=lambda x: -x[1])[0][0]
    else:
        from datetime import datetime
        inferred_year = str(datetime.now().year)
    
    # 转换为 (month, day, original) 元组用于排序
    parsed = []
    for d in dates_found:
        parts = d.split()
        month = month_map.get(parts[0], 0)
        day = int(parts[1])
        parsed.append((month, day, d))
    
    parsed.sort()
    unique_dates = sorted(set(dates_found), key=lambda x: (month_map.get(x.split()[0], 0), int(x.split()[1])))
    
    if not unique_dates:
        return [], '未知'
    
    # 格式化起始和结束日期
    def fmt(date_str, year):
        parts = date_str.split()
        m = month_map.get(parts[0], 0)
        d = int(parts[1])
        return f"{year}年{m}月{d}日"
    
    start = fmt(unique_dates[0], inferred_year)
    end = fmt(unique_dates[-1], inferred_year)
    date_range = f"{start} ~ {end}"
    
    return unique_dates, date_range

def generate_report(project_name, text, lines, project_type_key, project_type_name, role_map, mention_counter,
                    version_issues, qty_evolution, deps, cross_signals, action_items,
                    quality_metrics, risks, governance, dates, date_range):
    """生成报告"""
    roles_grouped = defaultdict(list)
    for person, role in role_map.items():
        roles_grouped[role].append(person)
    
    report = f"""# {project_name} 深度上下文挖掘报告

## 项目概况

| 指标 | 数值 |
|------|------|
| 项目名称 | {project_name} |
| 项目类型 | {project_type_name} |
| 分析文本行数 | {len(lines)} |
| 分析文本字符数 | {len(text):,} |
| 时间范围 | {date_range} |
| 识别核心成员 | {len(role_map)} |

## 一、团队角色图谱

"""
    for role, members in sorted(roles_grouped.items()):
        report += f"### {role}\n"
        for m in members:
            report += f"- {m} (被@{mention_counter.get(m, 0)}次)\n"
        report += "\n"
    
    top3 = [(p, c) for p, c in mention_counter.most_common(3) if is_person_name(p)]
    if len(top3) >= 2:
        report += "### 核心协作关系\n"
        report += f"- **高频协作链**: 问题/需求 → @{top3[0][0]} → 执行/推进 → @{top3[1][0]}\n"
        report += f"- **关键决策者**: @{top3[0][0]} (被@最多，{top3[0][1]}次)\n"
        report += "\n"
    
    if version_issues:
        report += "## 二、版本/发布迭代追踪\n\n"
        report += "| 日期 | 版本/标识 | 问题摘要 | 有解决迹象 |\n"
        report += "|------|----------|----------|------------|\n"
        for issue in version_issues[:12]:
            resolved = "✅" if issue['resolved'] else "❓"
            report += f"| {issue['date']} | {issue['version']} | {issue['issue'][:50]}... | {resolved} |\n"
        report += "\n"
    
    if qty_evolution:
        report += "## 三、数量/规模演变\n\n```\n"
        for date, desc in qty_evolution[:10]:
            report += f"[{date}] {desc}\n"
        report += "```\n\n"
    
    if deps:
        report += "## 四、外部依赖与合作伙伴\n\n```\n"
        for line in deps[:12]:
            report += f"- {line}\n"
        report += "```\n\n"
    
    if cross_signals:
        report += "## 五、跨项目/跨团队协作信号\n\n```\n"
        for line in cross_signals[:10]:
            report += f"- {line}\n"
        report += "```\n\n"
    
    if action_items:
        report += "## 六、行动项与待办追踪\n\n```\n"
        for line in action_items[:12]:
            report += f"- {line}\n"
        report += "```\n\n"
    
    if quality_metrics:
        report += "## 七、质量/性能指标\n\n```\n"
        for line in quality_metrics[:10]:
            report += f"- {line}\n"
        report += "```\n\n"
    
    if risks:
        report += "## 八、风险与延期预警\n\n```\n"
        for line in risks[:12]:
            report += f"- {line}\n"
        report += "```\n\n"
    
    if governance:
        report += "## 九、项目治理机制\n\n"
        for i, g in enumerate(governance[:3]):
            report += f"### 治理规则 {i+1}\n```\n{g[:350]}\n```\n\n"
    
    report += """## 十、关键发现总结

"""
    findings = []
    idx = 1
    if version_issues:
        findings.append(f"{idx}. **版本/发布稳定性**: 记录了版本迭代过程中的问题，存在发布风险或回归问题。")
        idx += 1
    if deps:
        findings.append(f"{idx}. **外部依赖复杂度**: 存在多个外部依赖方，需关注交付风险和合作关系。")
        idx += 1
    if cross_signals:
        findings.append(f"{idx}. **跨项目资源竞争**: 存在与其他项目/团队的资源协调需求。")
        idx += 1
    if risks:
        findings.append(f"{idx}. **进度风险**: 存在延期、瓶颈或阻塞项，需重点关注关键路径。")
        idx += 1
    if quality_metrics:
        findings.append(f"{idx}. **质量指标波动**: 质量/性能数据有波动，需持续监控。")
        idx += 1
    if governance:
        findings.append(f"{idx}. **项目治理**: 已建立一定的协作规范和沟通机制。")
        idx += 1
    
    if not findings:
        findings.append("1. **项目活跃度高**: 群内沟通频繁，信息流转较活跃。")
        findings.append("2. **建议**: 可针对具体维度（问题、决策、风险）做进一步定向分析。")
    
    for f in findings:
        report += f + "\n"
    
    report += f"""
## 项目上下文全景图

```
项目名称: {project_name}
类型: {project_type_name}
时间跨度: {date_range}

核心角色:
"""
    for role, members in list(roles_grouped.items())[:5]:
        report += f"  {role}: {', '.join(members[:3])}\n"
    
    report += """
关键链路:
  问题发现 → 责任人响应 → 方案讨论 → 验证闭环
  
外部依赖:
  供应商/合作方 → 交付风险 → 备选方案

风险雷达:
  ⚠️ 进度延期   ⚠️ 资源竞争   ⚠️ 质量波动   ⚠️ 需求变更
```
"""
    
    return report

def main():
    parser = argparse.ArgumentParser(description='通用项目聊天记录深度上下文挖掘（支持21种项目类型）')
    parser.add_argument('--input', '-i', required=True, help='输入聊天记录文本文件')
    parser.add_argument('--output', '-o', required=True, help='输出分析报告路径')
    parser.add_argument('--project-name', '-p', default='项目', help='项目名称')
    args = parser.parse_args()
    
    with open(args.input, 'r') as f:
        text = f.read()
    
    # Deduplicate before analysis
    text = dedup_lines(text)
    
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 2]
    
    project_type_key, project_type_name = detect_project_type(text)
    print(f"[INFO] 检测到项目类型: {project_type_name} (key={project_type_key})")
    
    role_hints = get_role_hints(project_type_key)
    role_map, mention_counter = infer_roles(text, lines, role_hints)
    print(f"[INFO] 识别核心成员: {len(role_map)} 人")
    
    version_issues = extract_version_issues(lines, project_type_key)
    qty_evolution = extract_quantity_evolution(lines)
    deps = extract_external_dependencies(lines, project_type_key)
    cross_signals = extract_cross_project_signals(lines)
    action_items = extract_action_items(lines)
    quality_metrics = extract_quality_metrics(lines, project_type_key)
    risks = extract_risks(lines)
    governance = extract_governance(lines)
    dates, date_range = extract_dates(text)
    
    print(f"[INFO] 版本问题: {len(version_issues)} | 数量变化: {len(qty_evolution)} | 外部依赖: {len(deps)}")
    print(f"[INFO] 跨项目信号: {len(cross_signals)} | 行动项: {len(action_items)} | 质量指标: {len(quality_metrics)}")
    print(f"[INFO] 风险: {len(risks)} | 治理机制: {len(governance)} | 时间范围: {date_range}")
    
    report = generate_report(
        args.project_name, text, lines, project_type_key, project_type_name, role_map, mention_counter,
        version_issues, qty_evolution, deps, cross_signals, action_items,
        quality_metrics, risks, governance, dates, date_range
    )
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        f.write(report)
    
    print(f"[DONE] 报告已保存: {args.output}")

if __name__ == '__main__':
    main()
