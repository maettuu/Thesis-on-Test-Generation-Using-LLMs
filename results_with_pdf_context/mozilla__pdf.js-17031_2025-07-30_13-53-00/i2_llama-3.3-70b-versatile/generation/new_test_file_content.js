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

  it("should not block the UI when changing font size", async () => {
    const { AnnotationEditor } = await import("./editor.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { PDFPageProxy } = await import("../../display/api.js");

    const uiManager = new AnnotationEditorUIManager();
    const pageProxy = new PDFPageProxy(1, 100, 100);
    const editor = new (class extends AnnotationEditor {
      moveInDOM() {
        this.parent?.moveEditorInDOM(this);
      }
    })({ parent: pageProxy, uiManager, id: 1, name: "test", x: 10, y: 10 });

    let blocked = false;
    const originalMoveInDOM = editor.moveInDOM;
    editor.moveInDOM = () => {
      blocked = true;
      originalMoveInDOM.call(editor);
    };

    const startTime = Date.now();
    editor.moveInDOM();
    while (blocked && Date.now() - startTime < 100) {
      await new Promise(resolve => globalThis.setTimeout(resolve, 10));
    }

    const { setTimeout } = await import("timers");
    const { moveInDOM } = await import("./editor.js");

    const patchedEditor = new (class extends AnnotationEditor {
      moveInDOM() {
        // Moving the editor in the DOM can be expensive, so we wait a bit before.
        // It's important to not block the UI (for example when changing the font
        // size in a FreeText).
        if (this.#moveInDOMTimeout) {
          clearTimeout(this.#moveInDOMTimeout);
        }
        this.#moveInDOMTimeout = setTimeout(() => {
          this.#moveInDOMTimeout = null;
          this.parent?.moveEditorInDOM(this);
        }, 0);
      }
    })({ parent: pageProxy, uiManager, id: 1, name: "test", x: 10, y: 10 });

    blocked = false;
    const originalPatchedMoveInDOM = patchedEditor.moveInDOM;
    patchedEditor.moveInDOM = () => {
      blocked = true;
      originalPatchedMoveInDOM.call(patchedEditor);
    };

    const patchedStartTime = Date.now();
    patchedEditor.moveInDOM();
    while (blocked && Date.now() - patchedStartTime < 100) {
      await new Promise(resolve => globalThis.setTimeout(resolve, 10));
    }

    expect(blocked).toBe(false);
  });
});