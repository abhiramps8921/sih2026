export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      credentials: 'same-origin',
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch {
    throw new Error(
      'Cannot reach the local server. Check that the Python API is running, then retry.',
    );
  }
  const text = await response.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error('The local API is unavailable. Start the Python server and retry.');
  }
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((e) => e.msg).join('. ')
          : 'This request could not be completed. Please retry.',
    );
  }
  return body;
}
export const send = (path, method, body) => api(path, { method, body: JSON.stringify(body) });
