async function fetch_chunks(patch) {
  const url = 'https://uplift.shipit.staging.mozilla-releng.net/coverage/chunks_for_patch';
  let response = await fetch(url, {
    method: 'POST',
    body: patch,
    headers: {
      'Content-Type': 'text/plain',
    },
  });
  return await response.json();
}

async function main() {
  await new Promise(resolve => window.onload = resolve);

  document.getElementById('go').onclick = async function() {
    const mapping = await fetch_chunks(document.getElementById('patch').value);

    let output = document.createElement('div');
    output.id = 'output';

    let all_chunks = new Set();
    for (let [path, chunks] of Object.entries(mapping)) {
      for (let chunk of chunks) {
          all_chunks.add(chunk);
      }
    }

    output.textContent = Array.from(all_chunks).sort().join(', ');
    document.getElementById('output').replaceWith(output);
  };
}

main();
