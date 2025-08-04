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

  it("should change mouse cursor when resizing from different edges", async () => {
    const { PDFDocument, PDFViewer } = await import("../../display/api.js");
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { PDFPageProxy } = await import("../../display/display_utils.js");
    const puppeteer = await import('puppeteer');

    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    const viewer = new PDFViewer({
      container: page.contentFrame(),
      viewerWidth: 800,
      viewerHeight: 600,
    });

    // Load test PDF with image
    const pdfDoc = await PDFDocument.load(await fetch('test.pdf'));
    const pageProxy = await pdfDoc.getPage(1);
    await viewer.setDocument(pdfDoc);
    await pageProxy.render({});

    // Add image annotation
    const editor = new AnnotationEditor({
      annotationElementId: "test-image",
      uiManager: new AnnotationEditorUIManager(),
      rotation: 0,
      x: 100,
      y: 100,
      width: 200,
      height: 150,
    });

    editor.select();
    editor.makeResizable();

    // Test top-left resize
    await page.mouse.move(100, 100);
    await page.mouse.down();
    await page.mouse.move(150, 150);
    await page.mouse.up();

    const cursorStyle = await page.evaluate(() => {
      return document.querySelector('.selectedEditor').style.cursor;
    });

    expect(cursorStyle).toBe('nwse-resize');

    await browser.close();
  });
});