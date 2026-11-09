// Pulls the activity list, icons and word lists out of index.html as JSON for make_printables.py
const fs = require("fs");
const html = fs.readFileSync(__dirname + "/../index.html", "utf8");
const grab = (start, end) => { const i = html.indexOf(start); const j = html.indexOf(end, i); return html.slice(i, j + end.length); };
const src = grab("const ACTIVITIES = [", "];") + "\n" + grab("const ICON_PATHS = {", "};") + "\n" + grab("const L = {", "\n};") + "\n" + grab("const SCREENS = {", "\n};");
const out = new Function(src + "\nreturn {ACTIVITIES, ICON_PATHS, L, SCREENS};")();
process.stdout.write(JSON.stringify(out));
