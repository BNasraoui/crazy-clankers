import { lang } from './i18n';
import type { Speaker } from './quips';

// Every fare gets a parody name from its type's pool. Both languages list the same
// number of names, so a passenger keeps their place in the pool when the language
// changes. The short name (the first name; all of a Chinese one) goes on the want panel.
type Pools = Record<Exclude<Speaker, 'cab'>, string[]>;

const EN: Pools = {
  techbro: [
    'Brayden Seedround', 'Tanner Tokenomics', 'Colt Coldplunge', 'Ryder Hypergrowth', 'Blake Vestington',
    'Hunter Pivotson', 'Trent Dataroom', 'Kyle Unicorn', 'Bryce Sprintly', 'Jaxon Tenex', 'Chase Synergy',
  ],
  cmo: [
    'Madison Funnel', 'Brooklyn Rebrand', 'Sienna Synergy', 'Kaia Clickthrough', 'Vivi Impressions',
    'Bella Brandvoice', 'Lux Lifestyle', 'Cammie Campaign', 'Ivy Influence', 'Mia Metrics',
  ],
  ceo: [
    'Grant Grindstone', 'Rex Layoffs', 'Sterling Burnout', 'Preston Quarterly', 'Damien Headcount',
    'Thorne Ultimatum', 'Victor Overtime', 'Conrad Deadline', 'Bradley Returntooffice', 'Hayes Hardcore',
  ],
  founder: [
    'Pivot McRunway', 'Jamie Stealthmode', 'Ash Burnrate', 'Mo Valuation', 'Robin Bridgeround',
    'Casey Cliffvest', 'Devon Demoday', 'Riley Prerevenue', 'Sasha Safenote', 'Jordan Termsheet',
  ],
  sweater: [
    'Sal Oltmann', 'Cardigan Sal', 'Hal Tmanner', 'Sol Ultman', 'Grey Crewneck',
    'Sammy Sevtrillion', 'Altie Nonprofit', 'Board Rehire', 'Sal Eyeballscan',
  ],
  rocket: [
    'Elron Tusk', 'Melon Dusk', 'Eon Husk', 'Leon Marsk', 'Elmo Tusk',
    'Nelo Must', 'Elongated Muskrat', 'Tweety Launchpad', 'Neon Husk',
  ],
  safety: [
    'Dairy Amodest', 'Ario Amode', 'Hedge Riskworth', 'Red-Team Ted', 'Con Stitution',
    'Saffo Tee', 'Alignment Al', 'Cautious Carlo', 'Paul Icy',
  ],
};

const ZH: Pools = {
  techbro: ['范融资', '梁天使', '王A轮', '赵估值', '孙增长', '周闭环', '吴赋能', '郑抓手', '钱冷萃', '何赛道', '冯对齐'],
  cmo: ['林流量', '苏滤镜', '白美颜', '安打卡', '唐种草', '夏出圈', '许热搜', '温点赞', '方出片', '江氛围'],
  ceo: ['龙傲天', '冷总', '顾裁员', '黄狼性', '钟福报', '严绩效', '厉加班', '卓卷王', '霍优化', '贺毕业'],
  founder: ['胡画饼', '陈期权', '刘跑路', '周PPT', '何风口', '郑烧钱', '白天使', '高估值', '罗下沉', '韩路演'],
  sweater: ['奥特慢', '傲特曼', '灰卫衣', '萨·七万亿', '奥·非营利', '萨·回归', '奥·扫眼球', '萨·算力', '奥·宫斗'],
  rocket: ['马斯壳', '马上天', '马火星', '麻斯渴', '马一冲', '马推推', '马明年', '马X', '马发射'],
  safety: ['阿慢代', '阿莫怠', '安·对齐', '宪·法安', '慎·小心', '稳·阿莫', '万字·达', '慢一点', '红队·泰'],
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
