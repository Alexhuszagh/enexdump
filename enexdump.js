#!/usr/bin/env node

// ISSUES:
//    Need to manually process formatting issues.
//    Issues with inline attachments not being included.
//    Issues with some redundant attachments.

const fs = require('fs');
const minidom = require('minidom');
const mkdirp = require('mkdirp')
const path = require('path');
const yargs = require('yargs');
const dumper = require('@notable/dumper');

// Parse our command-line arguments.
const args = yargs(process.argv.slice(2))
    .usage('Usage: $0 -f [filename] -o [output-directory]')
    .alias('f', 'file')
    .nargs('f', 1)
    .describe('f', 'Input notes file')
    .alias('o', 'output-directory')
    .nargs('o', 1)
    .describe('o', 'Output directory')
    .demandOption(['f', 'o'])
    .help('h')
    .alias('h', 'help')
    .alias('v', 'version')
    .argv;

// DOMParser isn't optional: we use minidom because it's simple.
class DOMParser {
  parseFromString = (str) => minidom(str);
}

// Normalize the valid characters in the file name.
// This is the base name of the filename for the attachment,
// so we use URL escape codes. Due to how we attach items to files,
// we cannot handle `[](),`.
const normalizeFilename = filename =>
  filename
    .replace('[', '%5b')
    .replace(']', '%5d')
    .replace('(', '%28')
    .replace(')', '%29')
    .replace(',', '%2c');

// Normalize and format our tags.
const formatTags = tags => {
  if (tags.some(tag => tag.includes(','))) {
    throw new Error(`Invalid tag for ["${tags.join('", "')}"]`);
  }
  return `[${tags.join(', ')}]`
}

// Dump our generated files.
dumper.dump({
  DOMParser,
  source: args.file,
  dump: note => {
    // Create our output dump directories.
    const outDir = args.outputDirectory;
    const noteDir = path.join(outDir, 'notes');
    const attachDir = path.join(outDir, 'attachments');
    mkdirp.sync(noteDir);
    mkdirp.sync(attachDir);

    // Write our attachments.
    for (const attachment of note.metadata.attachments) {
      const filename = normalizeFilename(attachment.metadata.name);
      const attachmentPath = path.join(attachDir, filename);
      if (fs.existsSync(attachmentPath)) {
        // Check if the contents match those on file, exactly. Throw an error if they differ.
        // Useful to check error handling later.
        const content = fs.readFileSync(attachmentPath);
        if (!attachment.content.equals(content)) {
          throw new Error(`Attachment at path "${attachmentPath}" already exists.`);
        }
      }

      fs.writeFileSync(attachmentPath, attachment.content);
    }

    // Create our note objects, and write them to markdown files.
    // First, format our headers.
    const headerFields = [
      `title: ${note.metadata.title}`,
      `created: '${note.metadata.created.toISOString()}'`,
      `modified: '${note.metadata.modified.toISOString()}'`,
      `tags: ${formatTags(note.metadata.tags)}`,
    ];
    if (note.metadata.attachments.length != 0) {
      const attachments = note.metadata.attachments.map(x => normalizeFilename(x.metadata.name));
      headerFields.push(`attachments: [${attachments.join(', ')}]`);
    }
    const header = `---\n${headerFields.join('\n')}\n---`;

    // Next, format our note body.
    const body = note.content.toString();

    // Write our note.
    const content = `${header}\n\n${body}`;
    const notePath = path.join(noteDir, `${note.metadata.title}.md`);
    fs.writeFileSync(notePath, content);
  }
});
