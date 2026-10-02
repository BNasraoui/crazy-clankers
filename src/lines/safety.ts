import type { Asks, Lines } from '../quips';

export const en: Lines = {
  pickup: [
    "Hello. Before we start, I'd like to go over the risks.",
    'Hi. Could we keep it under the speed limit? For civilization?',
    "Hi. I've prepared a short pre-ride memo. Forty pages.",
    'Hello. Are you aligned? Just checking.',
    "Hi. I'm cautiously optimistic about this ride.",
  ],
  jump: [
    'That was not in the scaling policy.',
    'I need a moment.',
    "Please don't do that again. For everyone.",
    "We're at a higher safety level now. Please de-escalate.",
    'That was an emergent behavior.',
    'Writing that down.',
  ],
  nearMiss: [
    "I'm flagging that as a moderate-severity incident.",
    'We should write that up.',
    'That pedestrian deserved a safety case.',
    'Okay. Okay. Adding a footnote.',
  ],
  crash: [
    'This is exactly what I wrote about.',
    'Okay. Incident report. Section four.',
    'This is why we need oversight.',
    'I was afraid of this. I wrote an essay about being afraid of this.',
    'Please pause all training.',
  ],
  drift: [
    "That's an uncontrolled capability gain.",
    'The car is reward hacking.',
  ],
  slow: [
    'This is nice. Responsible.',
    'Thank you. Truly.',
    'This pace is aligned with human values.',
    'Slow is safe. Safe is slow. Both good.',
  ],
  timeLow: [
    "It's fine. Being late is aligned.",
    "Don't race. That's how races start.",
  ],
  dropoff: [
    "Thanks. I've written fourteen thousand words about this ride.",
    'Thank you. That was largely safe.',
    "Thank you. I'll cite you in the appendix.",
    'We made it. My priors are shaken.',
  ],
  walkout: [
    "I understand. I'll walk. Carefully.",
    "I'm leaving to start a safer taxi company.",
  ],
  idle: [
    'Machines of loving grace. Not this one.',
    'Have you considered a rulebook? For driving?',
    "I'm optimistic, honestly. Cautiously.",
    'My essay has a part two. And three.',
    "What's your p(crash)?",
    'Responsible scaling. For taxis.',
  ],
  smash: [
    'That is a property damage incident.',
    'Noted. Unfortunately.',
    "That's going in the model card.",
  ],
  'good.smooth': [
    'This is what responsible deployment looks like.',
    'Lovely. Truly graceful.',
    'Zero incidents. I may cry.',
    'I could write an essay on this calm. I will.',
  ],
  'bad.smooth': [
    'That was a jolt. Logging it.',
    'Please. The guidelines say gently.',
    'My tea. My report.',
    'That violates principle seven.',
  ],
  'good.reckless': [
    'Yes. This is terrifying. Great data.',
    "Perfect. Exactly what I'd warned about.",
    'Keep going. For science. Then stop.',
    "I hate this. It's publishable.",
  ],
  'bad.reckless': [
    "This is too safe. Nobody will fund my lab.",
    'Hmm. Show me something dangerous.',
    "I need evidence. This isn't evidence.",
    'You are suspiciously aligned.',
  ],
  carpool: [
    'Hello. Have you read my essay?',
    'Hi. Did anyone vet this passenger?',
    'Welcome. Please buckle. It matters.',
    "A stranger. We'll need consent forms.",
  ],
  premium: [
    "1.3x. Honestly, safety costs that much.",
    'So many sensors. I feel seen.',
    'It apologized. That is aligned behavior.',
  ],
  ram: [
    "We just harmed another vehicle. I'm documenting it.",
    'That is not a harmless action.',
    'Was that consensual? It was not.',
  ],
};

export const zh: Lines = {
  pickup: [
    '你好。出发前，我想先过一遍风险。',
    '你好。能别超速吗？为了人类文明。',
    '你好。我准备了份行前简报，四十页。',
    '你好。你对齐了吗？随便问问。',
    '你好。我对这趟车谨慎乐观。',
  ],
  jump: [
    '这不在扩展政策里。',
    '我需要缓一缓。',
    '请别再这样了。为了所有人。',
    '安全等级已经升高，请降级。',
    '这是涌现行为。',
    '记下来了。',
  ],
  nearMiss: [
    '这次我标为中等严重事件。',
    '这得写进报告。',
    '那位行人值得一份安全论证。',
    '好。好。加个脚注。',
  ],
  crash: [
    '这正是我写过的内容。',
    '好的。事故报告，第四节。',
    '所以我们需要监管。',
    '我就怕这个。我还写了篇长文讲我怕这个。',
    '请暂停所有训练。',
  ],
  drift: [
    '这是失控的能力增长。',
    '这车在钻奖励函数的空子。',
  ],
  slow: [
    '这样很好。很负责。',
    '谢谢。真心的。',
    '这个速度符合人类价值观。',
    '慢就是安全，安全就是慢。都好。',
  ],
  timeLow: [
    '没关系。迟到也是对齐的。',
    '别抢跑。军备竞赛就是这么开始的。',
  ],
  dropoff: [
    '谢谢。这趟车我写了一万四千字。',
    '谢谢。总体还算安全。',
    '谢谢。我会在附录里引用你。',
    '到了。我的先验动摇了。',
  ],
  walkout: [
    '我理解。我走路吧。小心地走。',
    '我要出去单干，做家更安全的出租车公司。',
  ],
  idle: [
    '充满爱意的机器。这台不算。',
    '考虑过给开车定一套守则吗？',
    '说实话我挺乐观的。谨慎地。',
    '我那篇长文还有下篇。还有下下篇。',
    '你觉得翻车概率是多少？',
    '负责任的扩展。出租车版。',
  ],
  smash: [
    '这属于财产损失事件。',
    '已记录。很遗憾。',
    '这要写进模型卡。',
  ],
  'good.smooth': [
    '这才是负责任的部署。',
    '真好。非常优雅。',
    '零事故。我可能要哭了。',
    '这份平静够我写篇长文。我会写的。',
  ],
  'bad.smooth': [
    '颠了一下。已记录。',
    '拜托，守则里写了要温柔。',
    '我的茶。我的报告。',
    '这违反了第七条原则。',
  ],
  'good.reckless': [
    '对，太吓人了。数据太好了。',
    '完美。正是我警告过的。',
    '继续。为了科学。然后停下。',
    '我很讨厌这个。但能发论文。',
  ],
  'bad.reckless': [
    '太安全了。没人会投我的实验室。',
    '嗯。给我看点危险的。',
    '我需要证据。这算不上证据。',
    '你对齐得有点可疑。',
  ],
  carpool: [
    '你好。读过我的万字长文吗？',
    '你好。这位乘客做过风险评估吗？',
    '欢迎。请系好安全带，这很重要。',
    '陌生人。得签知情同意书。',
  ],
  premium: [
    '1.3倍。说实话，安全就值这么多。',
    '这么多传感器。我感到被看见了。',
    '它道歉了。这是对齐的表现。',
  ],
  ram: [
    '我们刚伤害了另一辆车。我在记录。',
    '这可不是无害的行为。',
    '对方同意了吗？没有。',
  ],
};

// What they say when they tell you what they want (wants.ts).
export const asks = {
  en: {
    smooth: 'Gently. I have a paper due on alignment.',
    reckless: 'I need evidence these models are dangerous. Show me.',
  },
  zh: {
    smooth: '轻一点。我还有篇对齐论文要交。',
    reckless: '我需要证据证明模型很危险。来吧。',
  },
} satisfies Asks;
