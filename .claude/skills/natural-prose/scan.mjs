#!/usr/bin/env node
// natural-prose scanner.
//
//   node scan.mjs <path...> [--lang en|uk] [--top N] [--min N]
//
// <path> may be a directory or a file. .html is read as a page: <main> if there
// is one, tables stripped, and only <p> text counted — spec-table and form-label
// typography is deliberate and must not be counted as prose. .md/.txt/.mjs/.js
// are read as text, with code and front matter stripped for the source case.
//
// Reports three things, in the order they should be acted on:
//   1. shared phrasing — one string reaching many pages, so one edit fixes all
//   2. construction density, against the healthy range
//   3. worst pages, so the manual pass has an order
import fs from 'node:fs'
import path from 'node:path'

const argv = process.argv.slice(2)
const flag = (n, d) => {
  const i = argv.indexOf('--' + n)
  return i === -1 ? d : argv[i + 1]
}
const LANG = flag('lang', 'en')
const TOP = +flag('top', 25)
const MIN_PAGES = +flag('min', 5)
const targets = argv.filter((a, i) => !a.startsWith('--') && !argv[i - 1]?.startsWith('--'))
if (!targets.length) {
  console.error('usage: node scan.mjs <path...> [--lang en|uk] [--top N] [--min N]')
  process.exit(1)
}

const EXT = /\.(html?|md|txt|mjs|js|ts|tsx|jsx)$/i
const files = []
for (const t of targets) {
  if (!fs.existsSync(t)) { console.error('no such path: ' + t); process.exit(1) }
  if (fs.statSync(t).isFile()) { files.push(t); continue }
  ;(function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (e.isDirectory()) { if (!/node_modules|\.git$/.test(e.name)) walk(p) }
      else if (EXT.test(e.name)) files.push(p)
    }
  })(t)
}

const unent = (x) =>
  x.replace(/<[^>]+>/g, ' ').replace(/&#x27;|&#39;|&rsquo;/g, "'").replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ').replace(/&[a-z]+;|&#\d+;/gi, ' ').replace(/\s+/g, ' ').trim()

// Pull running prose out of a file. HTML: paragraph text only. Source modules:
// the string literals, which is where the copy lives in a content pipeline.
function prose(file) {
  const raw = fs.readFileSync(file, 'utf8')
  if (/\.html?$/i.test(file)) {
    const main = (raw.match(/<main[\s\S]*?<\/main>/) || [raw])[0].replace(/<script[\s\S]*?<\/script>/g, ' ')
    const noTables = main.replace(/<table[\s\S]*?<\/table>/g, ' ')
    return [...noTables.matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/g)].map((m) => unent(m[1])).filter(Boolean).join(' ')
  }
  if (/\.(mjs|js|ts|tsx|jsx)$/i.test(file)) {
    const body = raw.replace(/^\s*\/\/.*$/gm, '')
    const lits = [...body.matchAll(/'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"/g)]
      .map((m) => (m[1] ?? m[2] ?? '').replace(/\\n/g, ' '))
      .filter((s) => s.split(' ').length > 4 && !/^[\w./#-]+$/.test(s))
    return unent(lits.join(' '))
  }
  return unent(raw.replace(/^---[\s\S]*?^---/m, ' ').replace(/```[\s\S]*?```/g, ' '))
}

const PATTERNS = {
  en: {
    'em dash in prose': [/—/g, 1, 3],
    '"rather than"': [/\brather than\b/gi, 0, 1],
    // A true pseudo-cleft fronts a whole clause as the subject of "is": "What
    // comes back is a quotation." An ordinary noun clause — "what the material
    // does in a fire", "what the room is for" — is plain English and must not be
    // counted. The discriminator is a lexical verb inside the clause AND a
    // following copula; a first pass without it reported 118 hits on this corpus
    // where about a dozen were real.
    'pseudo-cleft — "what X does is"': [
      /\bwhat\b[^.;:!?]{3,60}?\b(?:does|do|did|matters|changes|counts|comes|goes|moves|has|have|gives?|covers?|requires?|happens|separates|decides|delivers|means|makes?|leaves?|adds?|carries)\b[^.;:!?]{0,30}?\bis\b|\bwhat is\b[^.;:!?]{5,50}?\bis\b/gi,
      0, 0.5,
    ],
    'it-cleft — "it is X that"': [/\bit (?:is|was) (?:the |a |an )?[^.,;:]{2,40}? that\b/gi, 0, 0.5],
    '"and it is …"': [/\band it is\b/gi, 0, 0.3],
    '"which is" / "which is why"': [/\bwhich (?:is|are|means|was)\b/gi, 0, 0.8],
    // Only a tell when it is a reflex. A page whose argument IS a correction
    // ("a frosted panel is not a dark one", "this is not security film") earns
    // the construction, and stripping it damages the writing. Judge by whether
    // it repeats inside one page, not by the corpus rate.
    '"is not a …" (negative definition)': [/\bis not (?:a|an|the)\b/gi, 0, 1.2],
    '"it is worth"': [/\bit is worth\b/gi, 0, 0.2],
    '"is the one that/which"': [/\bis the one (?:that|which)\b/gi, 0, 0.2],
    'fronted "Where …, it/the"': [/\bWhere [^.,;:]{5,60}?, (?:it|the|that)\b/g, 0, 0.2],
    '"not only … but also"': [/\bnot only\b[^.]{0,60}\bbut (?:also|)\b/gi, 0, 0.1],
    '"serves as" / "plays a role"': [/\b(?:serves as|plays a (?:key |vital |crucial |important )?role)\b/gi, 0, 0.1],
    '"delve|leverage|robust|seamless"': [/\b(?:delve|delves|leverage|leverages|robust|seamless|seamlessly)\b/gi, 0, 0.1],
  },
  uk: {
    'тире в прозі': [/—/g, 1, 4],
    '"є ключовим/важливим"': [/\bє (?:ключов|важлив|основн|невід'ємн)\w*/gi, 0, 0.3],
    '"відіграє роль"': [/\bвідіграє\s+\S*\s*роль/gi, 0, 0.1],
    '"варто зазначити/відзначити"': [/\bварто (?:зазначити|відзначити|згадати|пам'ятати)\b/gi, 0, 0.2],
    '"не лише … але й"': [/\bне лише\b[^.]{0,70}\bале й\b/gi, 0, 0.1],
    'номіналізація "здійснює/проводить X"': [/\b(?:здійсню|провод|викону)\w+\s+(?:встановлен|монтаж|розрахун|обробк|перевірк)\w+/gi, 0, 0.2],
    '"дозволяє …"': [/\bдозволя[єю]\w*\b/gi, 0, 0.8],
    '"забезпечує"': [/\bзабезпечу[єю]\w*\b/gi, 0, 0.8],
    '"завдяки чому"': [/\bзавдяки (?:чому|цьому)\b/gi, 0, 0.2],
    '"у свою чергу"': [/\bу свою чергу\b/gi, 0, 0.1],
  },
}
const PAT = PATTERNS[LANG] || PATTERNS.en
const WORD = LANG === 'uk' ? /[^\p{L}\p{N}'’ -]/gu : /[^a-z0-9' -]/g

const docs = []
for (const f of files) {
  const text = prose(f)
  const w = text.split(/\s+/).filter(Boolean).length
  if (w < 120) continue
  let id = path.relative(process.cwd(), f).split(path.sep).join('/')
  id = id.replace(/\.next\/server\/app|\/\(site\)/g, '').replace(/\.html$/, '/').replace(/\/index\/$/, '/')
  docs.push({ id, text, w })
}
if (!docs.length) { console.error('no documents with >=120 words found'); process.exit(1) }
const TOTAL = docs.reduce((s, d) => s + d.w, 0)

// --- 1. shared phrasing -----------------------------------------------------
// Sentences repeated verbatim more than twice are a component (a CTA, a footer)
// and are excluded: they are meant to be identical. What we want is the phrase
// that recurs across pages inside otherwise different sentences.
const sent = new Map()
for (const d of docs)
  for (const s of d.text.split(/(?<=[.?!])\s+/)) {
    const k = s.trim().toLowerCase()
    if (k.length > 30) sent.set(k, (sent.get(k) || 0) + 1)
  }

const grams = new Map()
for (const d of docs)
  for (const s of d.text.split(/(?<=[.?!])\s+/)) {
    if ((sent.get(s.trim().toLowerCase()) || 0) > 2) continue
    const w = s.toLowerCase().replace(WORD, ' ').split(/\s+/).filter(Boolean)
    for (let n = 4; n <= 6; n++)
      for (let i = 0; i + n <= w.length; i++) {
        const g = w.slice(i, i + n).join(' ')
        let e = grams.get(g)
        if (!e) grams.set(g, (e = { c: 0, p: new Set() }))
        e.c++
        e.p.add(d.id)
      }
  }

// keep only the longest form of any phrase (a 6-gram implies its 4-grams)
const shared = [...grams.entries()].map(([g, e]) => ({ g, c: e.c, p: e.p.size }))
  .filter((x) => x.p >= MIN_PAGES).sort((a, b) => b.p - a.p || b.g.length - a.g.length)
const kept = []
for (const x of shared) if (!kept.some((k) => k.p === x.p && k.g.includes(x.g))) kept.push(x)

console.log('\n' + docs.length + ' documents · ' + TOTAL.toLocaleString() + ' prose words · lang=' + LANG)
console.log('\n1. SHARED PHRASING — one source string, many pages. Fix the module, not the pages.')
if (!kept.length) console.log('   (nothing on ' + MIN_PAGES + '+ documents)')
kept.slice(0, TOP).forEach((x) =>
  console.log('   ' + String(x.p).padStart(3) + ' docs  ' + String(x.c).padStart(3) + 'x   ' + x.g))

// --- 2. construction density ------------------------------------------------
console.log('\n2. CONSTRUCTIONS — per 1,000 prose words')
const rows = []
for (const [name, [re, lo, hi]] of Object.entries(PAT)) {
  let n = 0
  const pages = new Set()
  for (const d of docs) {
    const m = d.text.match(re)
    if (m) { n += m.length; pages.add(d.id) }
  }
  rows.push({ name, n, pages: pages.size, per: (n / TOTAL) * 1000, lo, hi })
}
rows.sort((a, b) => b.per / (b.hi || 0.05) - a.per / (a.hi || 0.05))
for (const r of rows) {
  const over = r.per > r.hi
  console.log('   ' + (over ? '!' : ' ') + ' ' + r.per.toFixed(2).padStart(5) + '  (healthy ' +
    (r.lo ? r.lo + '-' : '≤') + r.hi + ')  ' + String(r.n).padStart(4) + 'x on ' +
    String(r.pages).padStart(3) + ' docs   ' + r.name)
}

// --- 3. worst documents -----------------------------------------------------
const all = Object.values(PAT).map(([re]) => re)
for (const d of docs) {
  let n = 0
  for (const re of all) n += (d.text.match(re) || []).length
  d.hits = n
  d.per = (n / d.w) * 1000
}
console.log('\n3. WORST DOCUMENTS — edit in this order')
docs.sort((a, b) => b.per - a.per).slice(0, TOP).forEach((d) =>
  console.log('   ' + d.per.toFixed(1).padStart(5) + '   ' + String(d.hits).padStart(3) + ' in ' +
    String(d.w).padStart(5) + 'w   ' + d.id))
console.log('')
