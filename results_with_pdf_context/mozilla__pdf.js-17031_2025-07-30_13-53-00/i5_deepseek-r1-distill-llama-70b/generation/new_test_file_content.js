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

  it("should not block UI when changing font size in text editor", async () => {
    const { PDFDocument } = await import("../../core/document.js");
    const { Page } = await import("../../core/document.js");
    const { AnnotationEditor } = await import("../../display/editor/editor.js");

    // Create a mock PDF document and page
    const pdf = new PDFDocument(null, new PDFPage());
    const page = pdf.getPage(1);

    // Create an annotation editor instance
    const editor = new AnnotationEditor();
    editor.setMode(AnnotationEditor.EDIT_MODE.FREETEXT);
    editor.setPDFPage(page);
    editor.initialize();

    // Simulate font size change via slider
    const inputEvent = {
      target: {
        value: "24px", // Simulate changing font size
        getBoundingClientRect: () => ({ top: 0, left: 0 })
      }
    };

    // Create a promise to track when moveInDOM is called
    const moveInDOMSpy = jest.fn();
    const moveInDOMPromise = new Promise(resolve => {
      const originalMoveInDOM = editor.moveInDOM.bind(editor);
      editor.moveInDOM = (...args) => {
        moveInDOMSpy(...args);
        resolve();
      };
    });

    // Dispatch the input event to simulate font size change
    editor._onFontSizeChanged(inputEvent);

    // Wait for the moveInDOM to be called with debouncing
    await expect(moveInDOMPromise).resolves.toBeDefined();

    // Cleanup
    editor.destroy();
  });
});