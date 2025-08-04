#test/unit/editor_spec.js
/* Copyright 2022 Mozilla Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { CommandManager } from "../../src/display/editor/tools.js";

describe("editor", function () {
  describe("Command Manager", function () {
    it("should check undo/redo", function () {
      const manager = new CommandManager(4);
      let x = 0;
      const makeDoUndo = n => ({ cmd: () => (x += n), undo: () => (x -= n) });

      manager.add({ ...makeDoUndo(1), mustExec: true });
      expect(x).toEqual(1);

      manager.add({ ...makeDoUndo(2), mustExec: true });
      expect(x).toEqual(3);

      manager.add({ ...makeDoUndo(3), mustExec: true });
      expect(x).toEqual(6);

      manager.undo();
      expect(x).toEqual(3);

      manager.undo();
      expect(x).toEqual(1);

      manager.undo();
      expect(x).toEqual(0);

      manager.undo();
      expect(x).toEqual(0);

      manager.redo();
      expect(x).toEqual(1);

      manager.redo();
      expect(x).toEqual(3);

      manager.redo();
      expect(x).toEqual(6);

      manager.redo();
      expect(x).toEqual(6);

      manager.undo();
      expect(x).toEqual(3);

      manager.redo();
      expect(x).toEqual(6);
    });
  });

  it("should hit the limit of the manager", function () {
    const manager = new CommandManager(3);
    let x = 0;
    const makeDoUndo = n => ({ cmd: () => (x += n), undo: () => (x -= n) });

    manager.add({ ...makeDoUndo(1), mustExec: true }); // 1
    manager.add({ ...makeDoUndo(2), mustExec: true }); // 3
    manager.add({ ...makeDoUndo(3), mustExec: true }); // 6
    manager.add({ ...makeDoUndo(4), mustExec: true }); // 10
    expect(x).toEqual(10);

    manager.undo();
    manager.undo();
    expect(x).toEqual(3);

    manager.undo();
    expect(x).toEqual(1);

    manager.undo();
    expect(x).toEqual(1);

    manager.redo();
    manager.redo();
    expect(x).toEqual(6);
    manager.add({ ...makeDoUndo(5), mustExec: true });
    expect(x).toEqual(11);
  });

  it("should change cursor when resizing from different edges", async () => {
    const { AnnotationEditor, InkEditor, StampEditor } = await import("../../display/editor/editor.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");

    // Setup test HTML content
    const htmlContent = `
      <html>
        <head>
          <style>
            .resizer {
              width: 15px;
              height: 15px;
              position: absolute;
              z-index: 100;
            }
            .resizer.topLeft { cursor: nw-resize; }
            .resizer.topRight { cursor: ne-resize; }
            .resizer.bottomRight { cursor: se-resize; }
            .resizer.bottomLeft { cursor: sw-resize; }
            .resizer.topMiddle { cursor: n-resize; }
            .resizer.middleRight { cursor: e-resize; }
            .resizer.bottomMiddle { cursor: s-resize; }
            .resizer.middleLeft { cursor: w-resize; }
          </style>
        </head>
        <body></body>
      </html>
    `;

    // Create test page and editor
    const page = await new Promise(resolve => {
      const server = require('http').createServer((req, res) => {
        res.writeHead(200, {'Content-Type': 'text/html'});
        res.end(htmlContent);
      }).listen(0, 'localhost', () => {
        const port = server.address().port;
        resolve(`http://localhost:${port}`);
      });
    });

    // Initialize editor and page
    const editor = new StampEditor({
      parent: {},
      id: 'test-editor',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      rotation: 0,
      pageDimensions: [100, 100],
      pageTranslation: [0, 0]
    });

    // Test cursor changes
    const puppeteer = require('puppeteer');
    const browser = await puppeteer.launch();
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(page);

    // Click to activate editor
    await page.click('#test-editor');

    // Test top edge
    await page.hover('.resizers .topLeft');
    const topCursor = await page.evaluate(() => window.getComputedStyle(document.querySelector('.resizers .topLeft')).cursor);
    expect(topCursor).toBe('nw-resize');

    // Test right edge
    await page.hover('.resizers .topRight');
    const rightCursor = await page.evaluate(() => window.getComputedStyle(document.querySelector('.resizers .topRight')).cursor);
    expect(rightCursor).toBe('ne-resize');

    // Test bottom edge
    await page.hover('.resizers .bottomRight');
    const bottomCursor = await page.evaluate(() => window.getComputedStyle(document.querySelector('.resizers .bottomRight')).cursor);
    expect(bottomCursor).toBe('se-resize');

    // Test left edge
    await page.hover('.resizers .bottomLeft');
    const leftCursor = await page.evaluate(() => window.getComputedStyle(document.querySelector('.resizers .bottomLeft')).cursor);
    expect(leftCursor).toBe('sw-resize');

    // Cleanup
    await browser.close();
  });
});