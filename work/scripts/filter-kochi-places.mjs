import fs from 'node:fs';

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error('Expected input and output paths');

const excludedIds = new Set([
  'andhakaranazhi_beach',
  'athirapally_day_trip',
  'backwater_village_tour',
  'bolgatty_palace',
  'cherai_backwater_side',
  'cherai_beach',
  'cherai_toddy_shop',
  'chottanikkara_temple',
  'grand_hyatt_kochi_bolgatty',
  'infopark_food_court',
  'kadambrayar_riverside',
  'kalady',
  'kumbalangi_mangrove_walk',
  'kumbalangi_model_village',
  'kumbalam_backwaters',
  'marari_beach',
  'museum_of_kerala_history',
  'north_paravur_beach',
  'paravur_synagogue',
  'pathiramanal_island',
  'poornathrayeesa_temple',
  'thrikkakara_temple',
  'tripunithura_classical_music',
  'tripunithura_hill_palace',
  'tripunithura_puttu_kadai',
  'vypeen_island_cycle',
  'vypin_fishing_village',
  'vypin_lighthouse',
  'wonderla_kochi',
]);

const raw = fs.readFileSync(inputPath, 'utf8');
const blocks = [];
let depth = 0;
let start = -1;
let inString = false;
let escaped = false;

for (let index = 0; index < raw.length; index += 1) {
  const character = raw[index];
  if (inString) {
    if (escaped) escaped = false;
    else if (character === '\\') escaped = true;
    else if (character === '"') inString = false;
    continue;
  }
  if (character === '"') inString = true;
  else if (character === '{') {
    if (depth === 0) start = index;
    depth += 1;
  } else if (character === '}') {
    depth -= 1;
    if (depth === 0) blocks.push(raw.slice(start, index + 1));
  }
}

if (depth !== 0 || inString) throw new Error('Malformed JSON source');
const places = blocks.map((block) => ({ block, place: JSON.parse(block) }));
const presentIds = new Set(places.map(({ place }) => place.id));
const missingIds = [...excludedIds].filter((id) => !presentIds.has(id));
if (missingIds.length) throw new Error(`Missing excluded IDs: ${missingIds.join(', ')}`);

const kept = places.filter(({ place }) => !excludedIds.has(place.id));
if (places.length - kept.length !== excludedIds.size) {
  throw new Error('Excluded place count does not match unique excluded IDs');
}

const output = `[
${kept.map(({ block }) => `  ${block}`).join(',\n')}
]\n`;
JSON.parse(output);
fs.writeFileSync(outputPath, output, 'utf8');
