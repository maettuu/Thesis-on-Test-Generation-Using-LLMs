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
    const { PDFDocument } = await import("../../core/pdf_document.js");
    const { PDFPage } = await import("../../core/pdf_page.js");
    const { AnnotationEditor } = await import("../../display/editor/editor.js");

    // Create a mock PDF document with a page
    const pdf = new PDFDocument({
      length: 1,
      getInputStream: () => new ReadableStream({
        start(controller) { controller.close(); }
      }),
      get page() {
        return new PDFPage({
          pageIndex: 0,
          getInputStream: () => new ReadableStream({
            start(controller) { controller.close(); }
          }),
          getAnnotations: () => [],
          get viewport() {
            return {
              width: 100,
              height: 100,
              rotation: 0,
            };
          },
        });
      },
    });

    // Create an editor for an image annotation
    const editor = new AnnotationEditor({
      parent: pdf.getPage(0),
      parentDimensions: [100, 100],
      x: 0,
      y: 0,
      width: 50,
      height: 50,
      uiManager: {
        stopUndoAccumulation: () => {},
      },
    });

    // Initialize the editor and make it resizable
    editor.select();
    editor.makeResizable();

    // Check cursor styles for different resizers
    const resizers = editor.#resizersDiv.querySelectorAll(".resizer");
    expect(resizers[0].style.cursor).toBe("nwse-resize"); // topLeft
    expect(resizers[1].style.cursor).toBe("nesw-resize"); // topRight
    expect(resizers[2].style.cursor).toBe("nwse-resize"); // bottomRight
    expect(resizers[3].style.cursor).toBe("nesw-resize"); // bottomLeft
    if (resizers.length > 4) {
      expect(resizers[4].style.cursor).toBe("ns-resize"); // topMiddle
      expect(resizers[5].style.cursor).toBe("ew-resize"); // middleRight
      expect(resizers[6].style.cursor).toBe("ns-resize"); // bottomMiddle
      expect(resizers[7].style.cursor).toBe("ew-resize"); // middleLeft
    }
  });
});