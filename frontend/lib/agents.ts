export type AgentMeta = {
  name: string;
  short: string;
  description: string;
  avatarClass: string;
  dotClass: string;
  available: boolean;
};

export const AGENTS: Record<string, AgentMeta> = {
  counselor: {
    name: "辅导员",
    short: "辅",
    description: "总入口 · 答疑与分诊",
    avatarClass: "bg-[#f4e3dc] text-[#9c3d2a]",
    dotClass: "bg-[#b5462f]",
    available: true,
  },
  supervisor: {
    name: "学习督导",
    short: "督",
    description: "学情 · 计划 · 进度",
    avatarClass: "bg-[#e1efe8] text-[#2f5d50]",
    dotClass: "bg-[#3f7a66]",
    available: true,
  },
  examiner: {
    name: "出卷老师",
    short: "卷",
    description: "组卷 · 命题 · 模拟考",
    avatarClass: "bg-[#e5e8f7] text-[#3f4c8a]",
    dotClass: "bg-[#5262a4]",
    available: true,
  },
  collector: {
    name: "资料搜集",
    short: "采",
    description: "搜资料 · 收视频 · 导入文件",
    avatarClass: "bg-[#f2ead6] text-[#8a6a24]",
    dotClass: "bg-[#b08a33]",
    available: true,
  },
  organizer: {
    name: "资料整理",
    short: "整",
    description: "清洗 · 分块 · 向量入库",
    avatarClass: "bg-[#e8e6df] text-[#5f5a4d]",
    dotClass: "bg-[#8a8475]",
    available: true,
  },
  // 合并前的历史消息作者，保留映射避免旧对话显示成辅导员
  knowledge: {
    name: "答疑老师",
    short: "答",
    description: "知识树 · 技能卡片",
    avatarClass: "bg-[#e6edf5] text-[#3f5f7f]",
    dotClass: "bg-[#5b7fa6]",
    available: false,
  },
  grader: {
    name: "改卷老师",
    short: "改",
    description: "成绩 · 错题分布 · 水平变化",
    avatarClass: "bg-[#f3e6e9] text-[#8a3f52]",
    dotClass: "bg-[#a95a6d]",
    available: true,
  },
  tutor: {
    name: "答疑老师",
    short: "答",
    description: "讲题 · 方法 · 技能地图",
    avatarClass: "bg-[#e3f0ea] text-[#256b52]",
    dotClass: "bg-[#3f8f6c]",
    available: true,
  },
  user: {
    name: "我",
    short: "我",
    description: "",
    avatarClass: "bg-[#1f2328] text-white",
    dotClass: "bg-[#1f2328]",
    available: true,
  },
  system: {
    name: "系统",
    short: "·",
    description: "",
    avatarClass: "bg-[#ece8df] text-[#6b7280]",
    dotClass: "bg-[#9ca3af]",
    available: true,
  },
};

export const ROLE_OPTIONS = [
  { key: "counselor", label: "辅导员", hint: "默认模型即可" },
  { key: "supervisor", label: "学习督导", hint: "可用中等模型" },
  { key: "examiner", label: "出卷老师", hint: "建议强推理模型" },
  { key: "collector", label: "资料搜集", hint: "P1 已接入" },
  { key: "organizer", label: "资料整理", hint: "P1 已接入" },
  { key: "grader", label: "改卷老师", hint: "已接入" },
  { key: "tutor", label: "答疑老师", hint: "讲题与技能" },
];

export function agentMeta(author: string): AgentMeta {
  return AGENTS[author] ?? AGENTS.counselor;
}
