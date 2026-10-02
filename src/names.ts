import { lang } from './i18n';
import type { Speaker } from './quips';

// Every fare gets a parody name from its type's pool. Both languages list the same
// number of names, so a passenger keeps their place in the pool when the language
// changes. The short name (the first name; all of a Chinese one) goes on the want panel.
type Pools = Record<Exclude<Speaker, 'cab'>, string[]>;

const EN: Pools = {
  techbro: [
    'Brayden Seedround', 'Tanner Tokenomics', 'Colt Coldplunge', 'Ryder Hypergrowth', 'Blake Vestington',
    'Hunter Pivotson', 'Trent Dataroom', 'Kyle Unicorn', 'Bryce Sprintly', 'Jaxon Tenex',
    'Chase Synergy', 'Logan Lifelog', 'Cody Cofounder', 'Austin Biohack', 'Garrett Growthloop',
    'Dylan Disrupt', 'Mason Moonshot', 'Cooper Crunchbase', 'Wyatt Waitlist', 'Tyson Tractionman',
  ],
  cmo: [
    'Madison Funnel', 'Brooklyn Rebrand', 'Sienna Synergy', 'Kaia Clickthrough', 'Vivi Impressions',
    'Bella Brandvoice', 'Lux Lifestyle', 'Cammie Campaign', 'Ivy Influence', 'Mia Metrics',
    'Harper Hashtag', 'Skylar Storytell', 'Aria Engagement', 'Zoe Zeitgeist', 'Paige Viewsome',
    'Remi Reach', 'Nova Narrative', 'Stella Sponsored', 'Gigi Goviral', 'Coco Collab',
  ],
  ceo: [
    'Grant Grindstone', 'Rex Layoffs', 'Sterling Burnout', 'Preston Quarterly', 'Damien Headcount',
    'Thorne Ultimatum', 'Victor Overtime', 'Conrad Deadline', 'Bradley Returntooffice', 'Hayes Hardcore',
    'Lance Leverage', 'Duke Downsize', 'Royce Restructure', 'Pierce Productivity', 'Baron Bottomline',
    'Gordon Guidance', 'Ellis Efficiency', 'Maxwell Margins', 'Clint Cutbacks', 'Reid Reorg',
  ],
  founder: [
    'Pivot McRunway', 'Jamie Stealthmode', 'Ash Burnrate', 'Mo Valuation', 'Robin Bridgeround',
    'Casey Cliffvest', 'Devon Demoday', 'Riley Prerevenue', 'Sasha Safenote', 'Jordan Termsheet',
    'Alex Alphaversion', 'Taylor Tractionish', 'Morgan Minimumviable', 'Drew Disruption', 'Charlie Captable',
    'Parker Pitchdeck', 'Avery Acquihire', 'Rowan Runway', 'Emerson Exitplan', 'Sky Seedstage',
  ],
  // The soft-spoken visionary in muted knitwear: a type, never a real person (true of every pool).
  sweater: [
    'Cable Knitson', 'Merino Vance', 'Cashmere Cole', 'Purl Hopewell', 'Turtle Neckerson',
    'Fleece Futureman', 'Argyle Aster', 'Raglan Reyes', 'Woolsey Benevolent', 'Heather Horizon',
    'Muted Milo', 'Gentle Jasper', 'Patience Pendleton', 'Cozy Kingsley', 'Hush Hopwood',
    'Ember Eventually', 'Lowercase Lou', 'Soft Launch Sid', 'Quietly Quentin', 'Gray Matterson',
  ],
  // The rocket billionaire.
  rocket: [
    'Thrust Vanderbilt', 'Max Liftoff', 'Rex Orbiter', 'Boost McLaunch', 'Apogee Grant',
    'Cosmo Kingsford', 'Stellar Steele', 'Blaze Booster', 'Astro Ackerman', 'Nova Vanguard',
    'Gunner Gravity', 'Payload Pete', 'Titan Trillionsworth', 'Rocket Randall', 'Countdown Carl',
    'Zenith Zane', 'Ignition Ike', 'Moonbase Monty', 'Orbit Osborne', 'Launchpad Lars',
  ],
  // The worried AI safety researcher.
  safety: [
    'Hedge Riskworth', 'Red-Team Ted', 'Alignment Al', 'Cautious Carlo', 'Paul Icy',
    'Prudence Pause', 'Ward Guardrail', 'Wendy Worstcase', 'Barry Benchmark', 'Ellie Evals',
    'Sandy Sandbox', 'Percy Precaution', 'Hal Halt', 'Fran Failsafe', 'Kit Killswitch',
    'Otto Oversight', 'Vera Verify', 'Lyle Lowrisk', 'Morgan Mitigate', 'Constance Careful',
  ],
};

const ZH: Pools = {
  techbro: ['范融资', '梁天使', '王A轮', '赵估值', '孙增长', '周闭环', '吴赋能', '郑抓手', '钱冷萃', '何赛道', '冯对齐', '蒋复盘', '韩颗粒', '曹打法', '沈拉通', '杜沉淀', '罗链路', '彭心智', '谢拆解', '邱迭代'],
  cmo: ['林流量', '苏滤镜', '白美颜', '安打卡', '唐种草', '夏出圈', '许热搜', '温点赞', '方出片', '江氛围', '叶爆款', '秦文案', '顾私域', '陶调性', '宋破圈', '季话题', '邵转化', '纪曝光', '黎人设', '殷联名'],
  ceo: ['龙傲天', '冷总', '顾裁员', '黄狼性', '钟福报', '严绩效', '厉加班', '卓卷王', '霍优化', '贺毕业', '段降本', '崔增效', '雷调整', '万KPI', '姚扁平', '谭末位', '孔汇报', '魏对标', '翁拍板', '邹考勤'],
  founder: ['胡画饼', '陈期权', '刘跑路', '周PPT', '何风口', '郑烧钱', '白天使', '高估值', '罗下沉', '韩路演', '于BP', '戴风投', '石种子', '傅孵化', '薛愿景', '侯颠覆', '熊独角', '毛轻资', '邓卡位', '乔天使'],
  sweater: ['温愿景', '毛奇点', '程长期', '柔未来', '宋善意', '安低调', '霍佛系', '林小写', '严高领', '庄羊绒', '祝针织', '卫开衫', '乐慢慢', '和温吞', '秦使命', '文造福', '梁人类', '苗耐心', '简通用', '童轻声'],
  rocket: ['高升空', '唐推力', '程轨道', '卢发射', '邱星际', '冯点火', '于倒数', '万殖民', '贺登月', '骆载荷', '邵超重', '褚助推', '任回收', '龚近地', '殷远征', '韦火星', '柏星舰', '覃天梯', '晏引力', '岑太空'],
  safety: ['安对齐', '慎小心', '慢一点', '红队泰', '卫护栏', '严评测', '邵沙箱', '祁暂停', '闵风险', '苟稳妥', '冼兜底', '宁保守', '封急停', '查验证', '甘预案', '莫冒进', '鲍防线', '管监督', '汪最坏', '柏审慎'],
};

export const nameCount = (id: Exclude<Speaker, 'cab'>) => EN[id].length;

export function fullName(id: Exclude<Speaker, 'cab'>, i: number) {
  return (lang() === 'zh' ? ZH : EN)[id][i];
}

export function shortName(id: Exclude<Speaker, 'cab'>, i: number) {
  const name = fullName(id, i);
  return lang() === 'zh' ? name.replace('·', '') : name.split(' ')[0];
}

// Every Chinese name, so the label font can fetch their glyphs up front.
export const allZhNames = () => Object.values(ZH).flat().join('');
