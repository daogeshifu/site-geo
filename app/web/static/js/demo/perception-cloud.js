// ECharts and echarts-wordcloud are loaded from local vendor files by demo.html.
// The text list remains visible if chart initialization is unavailable.
let cloudObserver;
const activeCharts = new Set();

function drawCloud(stage) {
  const echarts = globalThis.echarts;
  const chartElement = stage.querySelector('.ai-word-cloud-chart');
  const words = [...stage.querySelectorAll('.ai-word')].map(item => item.textContent.trim()).filter(Boolean);
  const width = stage.clientWidth;
  const height = stage.clientHeight;
  if (!echarts || !chartElement || words.length < 3 || width < 120 || height < 100) return;

  const palette = stage.dataset.tone === 'limited'
    ? ['#a6493e', '#b65748', '#ca705c', '#91473f']
    : ['#166f60', '#278e79', '#3a9f88', '#276c63'];
  const chart = echarts.getInstanceByDom(chartElement) || echarts.init(chartElement, null, { renderer: 'canvas' });
  activeCharts.add(chart);
  chart.off('finished');
  chart.on('finished', () => stage.classList.add('is-rendered'));
  chart.resize();
  chart.setOption({
    animation: false,
    tooltip: { show: false },
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '98%',
      height: '94%',
      sizeRange: [11, Math.min(27, Math.max(21, Math.round(width / 15)))],
      rotationRange: [0, 0],
      gridSize: 3,
      drawOutOfBound: false,
      shrinkToFit: true,
      layoutAnimation: false,
      silent: true,
      textStyle: { fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif', fontWeight: 700 },
      data: words.map((name, index) => ({
        name,
        value: Math.max(10, 100 - index * 6),
        textStyle: { color: palette[index % palette.length] }
      }))
    }]
  }, true);
}

export function mountPerceptionClouds(host) {
  cloudObserver?.disconnect();
  activeCharts.forEach(chart => chart.dispose());
  activeCharts.clear();
  if (!host?.querySelectorAll || typeof document === 'undefined') return;
  const stages = [...host.querySelectorAll('.ai-word-cloud-stage')];
  if (!stages.length) return;
  if (typeof ResizeObserver === 'undefined') {
    stages.forEach(drawCloud);
    return;
  }
  cloudObserver = new ResizeObserver(entries => {
    entries.forEach(entry => {
      const stage = entry.target;
      const sizeKey = `${Math.round(entry.contentRect.width)}:${Math.round(entry.contentRect.height)}`;
      if (stage._lastCloudSize !== sizeKey) {
        stage._lastCloudSize = sizeKey;
        drawCloud(stage);
      }
    });
  });
  stages.forEach(stage => cloudObserver.observe(stage));
}
