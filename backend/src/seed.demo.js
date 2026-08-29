// Demo seed — NOT run automatically.
// Run with:  npm run seed:demo   (from backend/)
// Inserts 3 clearly-marked SAMPLE questions (one per subject) so the UI can be
// visually verified. These are placeholders to be replaced by real authored content.
import db from './db.js';
import { insertQuestion } from './questionRepo.js';

const samples = [
  {
    subject: 'CS', level: 'HL', topic: 'System fundamentals', subtopic: 'System lifecycle',
    paper_type: 'Paper 1', command_term: 'Outline', marks: 4, difficulty: 2,
    question: 'Outline the stages of the system lifecycle.', figure: '',
    answer: 'Investigation, analysis, design, development, testing, implementation, maintenance.',
    explanation: 'The system lifecycle breaks development into phases; each phase has deliverables that feed the next.',
    source: 'demo', tags: ['system lifecycle', 'demo']
  },
  {
    subject: 'Math', level: 'HL', topic: 'Calculus', subtopic: 'Differentiation',
    paper_type: 'Paper 1', command_term: 'Calculate', marks: 6, difficulty: 3,
    question: 'Find $\\frac{d}{dx}(x^3 \\sin x)$.', figure: '',
    answer: '$3x^2\\sin x + x^3\\cos x$',
    explanation: 'Apply the product rule: $(uv)\' = u\'v + uv\'$, with $u=x^3$, $v=\\sin x$.',
    source: 'demo', tags: ['differentiation', 'demo']
  },
  {
    subject: 'Physics', level: 'HL', topic: 'Mechanics', subtopic: 'Kinematics',
    paper_type: 'Paper 1', command_term: 'Calculate', marks: 5, difficulty: 2,
    question: 'A car accelerates uniformly from $0$ to $20\\,\\text{m s}^{-1}$ in $10\\,\\text{s}$. Calculate its acceleration.', figure: '',
    answer: '$a = \\frac{\\Delta v}{\\Delta t} = \\frac{20}{10} = 2\\,\\text{m s}^{-2}$',
    explanation: 'Uniform acceleration is the change in velocity over time.',
    source: 'demo', tags: ['kinematics', 'demo']
  }
];

async function main() {
  await db.init();
  await db.transaction(async () => {
    for (const s of samples) {
      await insertQuestion({ ...s, source: s.source || 'demo' }, { authored_by: 'demo' });
    }
  });
  console.log(`[seed:demo] inserted ${samples.length} demo questions.`);
}

main().catch((e) => {
  console.error('[seed:demo] failed:', e);
  process.exit(1);
});
