const table = document.querySelector('#works');
const rows = [...table.rows];
const filter = document.querySelector('#filter');
const order = document.querySelector('#order');
const sample = document.querySelector('#sample');
const count = document.querySelector('#row-count');

function updateWorks() {
  const query = filter.value.trim().toLowerCase();
  const sortKey = order.value;
  const visible = [];
  for (const row of rows) {
    const matches = row.cells[0].dataset.search.toLowerCase().includes(query);
    row.hidden = !matches || (sample.checked && row.dataset.sample !== '1');
    if (!row.hidden) visible.push(row);
  }
  const value = (row) => row.dataset[sortKey];
  const missing = (key) => key === '' || key === '—';
  visible.sort((first, second) => {
    const a = value(first), b = value(second);
    if (missing(a) || missing(b)) return Number(missing(a)) - Number(missing(b));
    return sortKey === 'date' ? b.localeCompare(a) : Number(b) - Number(a);
  });
  table.append(...visible);
  count.textContent = `${visible.length} 条`;
}

for (const element of [filter, order, sample]) element.addEventListener('input', updateWorks);
