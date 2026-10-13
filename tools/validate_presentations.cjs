const { chromium } = require("playwright");
const { pathToFileURL } = require("node:url");
const path = require("node:path");
const fs = require("node:fs");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ["--allow-file-access-from-files"],
  });
  const page = await browser.newPage({ viewport: { width: 540, height: 700 } }),
    errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(
    pathToFileURL(path.resolve("core/spatial/presentation.html")).href,
  );
  await page.waitForFunction(() => typeof window.updateCore === "function");
  const items = [
    {
      id: 1,
      title: "Preparar relatório",
      priority: "high",
      due: "2026-10-12T14:00",
    },
    { id: 2, title: "Revisar projeto", due: "2026-10-13T10:00" },
    { id: 3, title: "Organizar arquivos" },
  ];
  const models = [
    {
      kind: "weather",
      title: "CLIMA",
      city: "Porto Alegre",
      region: "Rio Grande do Sul",
      temperature: 19,
      condition: "Chuva",
      code: 61,
      rain: 80,
      wind: 12,
      humidity: 78,
      forecast: [{ date: "2026-10-11", max: 23, min: 16, rain: 80 }],
      source: "EXEMPLO DE TESTE",
    },
    {
      kind: "system",
      title: "SISTEMA",
      cpu_percent: 34,
      ram_percent: 71,
      gpu_percent: 12,
      cpu_temp_c: null,
      ram_used_gb: 11,
      ram_total_gb: 16,
      uptime: "2h 15m",
      process_count: 180,
      source: "EXEMPLO DE TESTE",
    },
    {
      kind: "tasks",
      title: "TAREFAS",
      count: 3,
      items,
      source: "EXEMPLO DE TESTE",
    },
    { kind: "calendar", title: "AGENDA", items, source: "EXEMPLO DE TESTE" },
    {
      kind: "files",
      title: "ARQUIVOS",
      text: "Arquivos de teste",
      source: "EXEMPLO DE TESTE",
    },
    {
      kind: "memory",
      title: "MEMÓRIA",
      text: "Preferência de teste",
      source: "EXEMPLO DE TESTE",
    },
    {
      kind: "search",
      title: "BUSCA",
      text: "Resultado de teste",
      source: "EXEMPLO DE TESTE",
    },
    {
      kind: "news",
      title: "NOTÍCIAS",
      items: [
        {
          title: "Pesquisa brasileira avança em ciência",
          detail: "Informações da primeira notícia. Fonte de teste.",
        },
        { title: "Segunda notícia", detail: "Outro assunto de teste." },
      ],
      source: "EXEMPLO DE TESTE",
    },
  ];
  const results = [];
  for (const model of models) {
    await page.evaluate((m) => window.updateCore(m), model);
    await page.waitForTimeout(2400);
    const result = await page.evaluate(() => {
      const c = document.querySelector("canvas"),
        gl = c.getContext("webgl2");
      const p = new Uint8Array(
        gl.drawingBufferWidth * gl.drawingBufferHeight * 4,
      );
      gl.readPixels(
        0,
        0,
        gl.drawingBufferWidth,
        gl.drawingBufferHeight,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        p,
      );
      let lit = 0;
      for (let i = 0; i < p.length; i += 4)
        if (p[i] + p[i + 1] + p[i + 2] > 65) lit++;
      return {
        kind: document.body.dataset.kind,
        lit,
        calls: document.body.dataset.drawCalls,
        overflow: document.documentElement.scrollWidth > innerWidth,
      };
    });
    if (result.lit < (model.kind === "news" ? 0 : 250) || result.overflow)
      throw Error(JSON.stringify(result));
    await page.screenshot({
      path: `validation/presentation-${model.kind}.png`,
    });
    results.push(result);
    if (model.kind !== "news") {
      const checksum = () =>
        page.evaluate(() => {
          const c = document.querySelector("canvas"),
            gl = c.getContext("webgl2"),
            p = new Uint8Array(
              gl.drawingBufferWidth * gl.drawingBufferHeight * 4,
            );
          gl.readPixels(
            0,
            0,
            gl.drawingBufferWidth,
            gl.drawingBufferHeight,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            p,
          );
          let sum = 0;
          for (let i = 0; i < p.length; i += 4)
            sum =
              (sum + (p[i] + p[i + 1] + p[i + 2]) * ((i % 997) + 1)) %
              2147483647;
          return sum;
        });
      const before = await checksum();
      await page.waitForTimeout(500);
      const after = await checksum();
      if (before === after) throw Error(model.kind + " animation is frozen");
      result.motion = true;
    }
  }
  await page.locator("#next-news").click();
  await page.waitForFunction(
    () =>
      document.querySelector(".record.selected h2")?.textContent ===
      "Segunda notícia",
  );
  if (
    (await page.locator(".record.selected h2").innerText()) !==
    "Segunda notícia"
  )
    throw Error("Selection failed");
  await page.evaluate(() => window.narratePresentation("A primeira notícia"));
  if (
    !(await page.locator(".record").first().getAttribute("class")).includes(
      "selected",
    )
  )
    throw Error("Narration focus failed");
  await page.evaluate(() =>
    window.updateCore({
      kind: "data",
      title: "TESTE",
      items: [{ title: "<script>window.pwned=true</script>" }],
    }),
  );
  if (await page.evaluate(() => !!window.pwned)) throw Error("Unsafe text");
  await page.evaluate(
    (m) =>
      window.updateCore({
        ...m,
        narrationDriven: true,
        city: "Teste de reprodução",
      }),
    models[0],
  );
  await page.waitForTimeout(500);
  if ((await page.locator("#summary h1").innerText()) !== "")
    throw Error("Data appeared before playback");
  await page.evaluate(() =>
    window.advancePresentation({
      elapsed: 1.1,
      cues: ["Temos dezenove graus"],
    }),
  );
  await page.waitForTimeout(150);
  if (!(await page.locator("#summary").innerText()).trim())
    throw Error("Playback did not reveal data");
  await page.evaluate(() => {
    window.cancelPresentation();
    window.advancePresentation({ elapsed: 20, cues: ["Nova notícia"] });
  });
  await page.waitForTimeout(60);
  const beforeCancel = await page.locator("#summary").innerText();
  await page.waitForTimeout(300);
  if ((await page.locator("#summary").innerText()) !== beforeCancel)
    throw Error("Cancelled playback changed data");
  const headline =
    "Esta é uma manchete longa para conferir que os caracteres aparecem durante a fala";
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.evaluate(
    (title) =>
      window.updateCore({
        kind: "news",
        title: "NOTÍCIAS",
        items: [
          {
            title,
            detail:
              "Resumo detalhado que também deve ser digitado e não aparecer inteiro de uma só vez.",
          },
        ],
        narrationDriven: true,
      }),
    headline,
  );
  await page.evaluate(() =>
    window.advancePresentation({ elapsed: 0.7, cues: [] }),
  );
  await page.waitForTimeout(120);
  const partial = await page.locator(".record.selected h2").innerText();
  if (!partial || partial === headline)
    throw Error("Headline is not typing progressively");
  await page.evaluate(() => window.finishPresentation());
  await page.waitForTimeout(60);
  if ((await page.locator(".record.selected h2").innerText()) === headline)
    throw Error("Speech end filled the headline instantly");
  if (
    (await page.evaluate(() => document.body.dataset.secondaryCore)) !== "false"
  )
    throw Error("Secondary hologram exists");
  for (const size of [
    { width: 360, height: 620 },
    { width: 900, height: 900 },
  ]) {
    await page.setViewportSize(size);
    await page.evaluate((m) => window.updateCore(m), models[0]);
    await page.waitForTimeout(400);
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Responsive overflow");
    await page.screenshot({
      path: `validation/presentation-weather-${size.width}.png`,
    });
  }
  if (errors.length) throw Error(errors.join("\n"));
  const resources = [];
  for (let i = 0; i < 12; i++) {
    await page.evaluate(
      (m) => window.updateCore(m),
      models[i % 2 ? 0 : models.length - 1],
    );
    await page.waitForTimeout(80);
    resources.push(
      await page.evaluate(() => Number(document.body.dataset.geometries)),
    );
  }
  const newsCounts = resources.filter((_, i) => i % 2 === 0);
  if (Math.max(...newsCounts) - Math.min(...newsCounts) > 3)
    throw Error("Geometry resources accumulated");
  fs.writeFileSync(
    "validation/presentation-results.json",
    JSON.stringify(results, null, 2),
  );
  console.log(JSON.stringify(results));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
