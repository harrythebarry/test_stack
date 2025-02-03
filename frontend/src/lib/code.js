/**
 * Processes code blocks in markdown content to handle file updates
 * @param {string} content - The markdown content containing code blocks
 * @param {boolean} partial - Whether the content is partial/incomplete
 * @returns {string} The processed content with encoded file updates
 */
export const fixCodeBlocks = (content, partial) => {
  if (!content) return content;

  const replaceB64 = (_, filename, content) => {
    const b64 = Buffer.from(JSON.stringify({ filename, content })).toString(
      'base64'
    );
    return `<file-update>${b64}</file-update>`;
  };

  content = content.replace(
    /```[\w.]+\n[#/]+ (\S+)\n([\s\S]+?)```/g,
    replaceB64
  );
  content = content.replace(
    /```[\w.]+\n[/*]+ (\S+) \*\/\n([\s\S]+?)```/g,
    replaceB64
  );
  content = content.replace(
    /```[\w.]+\n<!-- (\S+) -->\n([\s\S]+?)```/g,
    replaceB64
  );

  if (partial) {
    content = content.replace(
      /```[\s\S]+$/,
      '<file-loading>...</file-loading>'
    );
  }

  return content;
};
