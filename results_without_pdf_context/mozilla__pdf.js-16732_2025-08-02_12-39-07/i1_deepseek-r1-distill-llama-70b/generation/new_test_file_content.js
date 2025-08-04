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
    const { PDFDocument } = await import("../../core/document.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { PDFViewer } = await import("../../display/display_utils.js");
    const { AnnotationEditor } = await import("../../display/editor/editor.js");

    const pdf = await PDFDocument.load(
      new Uint8Array(await (await fetch("test.pdf")).arrayBuffer())
    );
    const viewer = new PDFViewer/pdf();
    const uiManager = new AnnotationEditorUIManager(viewer);
    const editor = new AnnotationEditor({
      parent: viewer,
      uiManager: uiManager,
      type: AnnotationEditorType.INITIAL,
      id: "test-editor",
      name: "test-editor",
    });

    editor.makeResizable();
    editor.select();

    const page = pdf.getPage(0);
    const viewport = page.getViewPort();

    const resizers = editor.div.querySelectorAll(".resizer");
    const cursorStyles = {
      topLeft: "nwse-resize",
      topRight: "nesw-resize",
      bottomRight: "nwse-resize",
      bottomLeft: "nesw-resize",
    };

    for (const resizer of resizers) {
      const name = resizer.classList[1];
      const event = new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        clientX: 0,
        clientY: 0,
      });

      resizer.dispatchEvent(event);
      await new Promise(resolve => setTimeout(resolve, 100));

      const cursor = window.getComputedStyle(resizer).cursor;
      expect(cursor).toBe(cursorStyles[name]);
    }
  });
});