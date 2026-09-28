// Olivia Moore 7C — timetable as at 11/09/2026. [subject, teacher, room]
const SUBJECTS = {
  "Registration": { short: "Reg",    icon: "🐴", color: "#B5835A" },
  "Maths":        { short: "Maths",  icon: "🔢", color: "#FF3E8A" },
  "English":      { short: "English",icon: "📖", color: "#7B4DFF" },
  "Science":      { short: "Science",icon: "🔬", color: "#10B96E" },
  "French":       { short: "French", icon: "🥐", color: "#2F7BEA" },
  "RE":           { short: "RE",     icon: "🕊️", color: "#FF9A1F" },
  "Music":        { short: "Music",  icon: "🎵", color: "#C636F0" },
  "PE":           { short: "PE",     icon: "🏇", color: "#EF2B45" },
  "History":      { short: "History",icon: "🏰", color: "#B8703A" },
  "Technology":   { short: "Tech",   icon: "🛠️", color: "#00A8C8" },
  "Drama":        { short: "Drama",  icon: "🎭", color: "#F25C05" },
  "Art":          { short: "Art",    icon: "🎨", color: "#F2B705" },
  "Geography":    { short: "Geog",   icon: "🌍", color: "#2A9D8F" },
  "Values":       { short: "Values", icon: "💛", color: "#9B5DE5" },
  "ICT":          { short: "ICT",    icon: "💻", color: "#3A6FF7" },
  "Literacy":     { short: "Literacy",icon: "✏️", color: "#E4479F" },
};
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const PERIODS = ["Reg", "1", "2", "3", "4", "5", "6"];
const REG = ["Registration", "CEG", "AGB"];
const TT = {
  Mon: [REG, ["RE","ETA","ZGC"], ["Maths","KMA","B1C"], ["Science","CEG","D1F"], ["Geography","RST","Z1A"], ["Literacy","FST","S1A"], null],
  Tue: [REG, ["Music","DJA","SGA"], ["Science","CEG","Z1D"], ["Art","EMO","AGB"], ["English","OBR","D1D"], ["Values","RMV","S1C"], null],
  Wed: [REG, ["PE","SEW",""], ["Technology","CWI","NGB"], ["Maths","KMA","B1C"], ["Values","APE","Z1C"], ["English","OBR","D1D"], null],
  Thu: [null, ["English","OBR","D1D"], ["Drama","CCL","SGC"], ["French","SMA","A1C"], ["Technology","EDA","D1H"], ["Science","CEG","D2E"], REG],
  Fri: [REG, ["History","JSI","ZGA"], ["French","EWI","A1B"], ["Maths","KMA","B1C"], ["ICT","CWI","D2B"], ["PE","KBR",""], null],
};
