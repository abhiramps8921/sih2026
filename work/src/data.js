export const photos = { coast: '/images/kochi.jpg', heritage: '/images/heritage.jpg', food: '/images/food.jpg' };
export const templates = [
  { id: 'slow-kochi', title: 'The slow side of Kochi', subtitle: 'Sea breezes, old streets & a really good cup of coffee.', days: 2, cost: 1800, category: 'Hidden gems', image: photos.coast, creator: 'Ananya M.', initials: 'AM', role: 'Kochi local', color: '#e9d6b5', slh: 92, tags: ['Culture', 'Food', 'Nature'], stops: ['nets', 'church', 'kashi', 'beach', 'palace', 'jewtown', 'cafe', 'promenade'], featured: true },
  { id: 'heritage-trail', title: 'Stories in every street', subtitle: 'A walk through the many worlds of Mattancherry.', days: 1, cost: 850, category: 'Culture & heritage', image: photos.heritage, creator: 'Arjun R.', initials: 'AR', role: 'History enthusiast', color: '#d5dfec', slh: 89, tags: ['Culture', 'Art'], stops: ['palace', 'jewtown', 'synagogue', 'cafe'] },
  { id: 'taste-kochi', title: 'A taste of the real Kochi', subtitle: 'Banana-leaf lunches, little cafés & big flavours.', days: 1, cost: 1100, category: 'Food trail', image: photos.food, creator: 'Meera K.', initials: 'MK', role: 'Food explorer', color: '#e7d5de', slh: 90, tags: ['Food', 'Culture'], stops: ['kashi', 'market', 'sadya', 'cafe'] },
  { id: 'coastal-reset', title: 'Salt air & slower mornings', subtitle: 'A little less rushing. A lot more waterfront.', days: 3, cost: 2600, category: 'Outdoors', image: photos.coast, creator: 'Dev P.', initials: 'DP', role: 'Weekend wanderer', color: '#d9e5c8', slh: 87, tags: ['Nature', 'Food'], stops: ['nets', 'beach', 'promenade', 'park', 'island', 'kashi', 'cafe', 'market', 'sadya'] },
];
export const interests = ['All experiences', 'Food', 'Culture', 'Nature', 'Art', 'Hidden gems'];
export const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
export function slhScore(slh) {
  if (!slh || ['safety', 'legitimacy', 'hygiene'].some(key => !Number.isFinite(slh[key]))) return null;
  return Math.round((slh.safety + slh.legitimacy + slh.hygiene) / 15 * 100);
}
