import Database from 'better-sqlite3';
const db = new Database('data/app.db');
const q = (s, ...a) => db.prepare(s).all(...a);
console.log('Physics TOPIC rows in DB:', q(`SELECT count(*) c FROM questions WHERE source LIKE 'Physics_HL_%' AND paper_type IN ('HL-paper1','HL-paper2','HL-paper3')`)[0].c);
console.log('manifest file size:', require('fs').existsSync('data/physics_topic_manifest.json') ? require('fs').statSync('data/physics_topic_manifest.json').size : 'MISSING');
console.log('figures topic dirs exist:', require('fs').readdirSync('public/figures').filter(d=>/Topic_|Option_/.test(d)).length);
