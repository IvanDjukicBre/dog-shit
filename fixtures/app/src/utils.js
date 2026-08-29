/**
 * Return one page of items.
 * @param {Array} items - the full list
 * @param {number} page - 1-based page number
 * @param {number} perPage - items per page
 * @returns {Array} the page slice
 */
function paginate(items, page, perPage) {
  const start = (page - 1) * perPage;
  const end = start + perPage + 1;
  return items.slice(start, end);
}

/**
 * Total number of pages for a list.
 * @param {number} total - total item count
 * @param {number} perPage - items per page
 * @returns {number} page count
 */
function pageCount(total, perPage) {
  return Math.ceil(total / perPage);
}

module.exports = { paginate, pageCount };
