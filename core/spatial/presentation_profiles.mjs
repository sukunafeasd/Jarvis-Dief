// Trusted visual vocabulary. Models provide data, never materials or geometry.
export const profiles = Object.freeze({
  weather: { accent:'#25d9fa', secondary:'#ffb93e', assembly:'condense', motion:'atmosphere' },
  tasks: { accent:'#2cf5ba', secondary:'#bd96ff', assembly:'segments', motion:'task-orbit' },
  calendar: { accent:'#ffbd45', secondary:'#19e0f0', assembly:'dial', motion:'time' },
  system: { accent:'#13def4', secondary:'#ff515c', assembly:'circuits', motion:'telemetry' },
  gmail: { accent:'#ff435a', secondary:'#3ce3ff', assembly:'envelope', motion:'mail' },
  whatsapp: { accent:'#27f0a2', secondary:'#75ffd2', assembly:'bubbles', motion:'conversation' },
  news: { accent:'#b6dce6', secondary:'#8cd9bc', assembly:'editorial', motion:'narration' },
  memory: { accent:'#bc83ff', secondary:'#36f1c8', assembly:'network', motion:'connections' },
  search: { accent:'#25edce', secondary:'#ffc345', assembly:'scan', motion:'sweep' },
  files: { accent:'#2bccff', secondary:'#46f5c7', assembly:'slabs', motion:'catalogue' },
  data: { accent:'#3cdfff', secondary:'#ffc04e', assembly:'columns', motion:'data' },
  status: { accent:'#b6dce6', secondary:'#8cd9bc', assembly:'checks', motion:'checks' },
});
export function profileFor(kind) { return profiles[kind] || profiles.data; }
