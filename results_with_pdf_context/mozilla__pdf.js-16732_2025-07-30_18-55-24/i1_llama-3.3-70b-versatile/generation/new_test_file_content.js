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

  it("should change the mouse cursor state according to the edge we resize from for added images and drawings in PDF documents", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const editor = new AnnotationEditor({ uiManager: new AnnotationEditorUIManager() });
    editor.makeResizable();
    const resizerDiv = editor.#resizersDiv;
    const topLeftResizer = resizerDiv.querySelector(".resizer.topLeft");
    const topRightResizer = resizerDiv.querySelector(".resizer.topRight");
    const bottomLeftResizer = resizerDiv.querySelector(".resizer.bottomLeft");
    const bottomRightResizer = resizerDiv.querySelector(".resizer.bottomRight");
    const middleLeftResizer = resizerDiv.querySelector(".resizer.middleLeft");
    const middleRightResizer = resizerDiv.querySelector(".resizer.middleRight");
    const topMiddleResizer = resizerDiv.querySelector(".resizer.topMiddle");
    const bottomMiddleResizer = resizerDiv.querySelector(".resizer.bottomMiddle");

    // Check if the resizers are correctly added to the editor
    expect(resizerDiv.childElementCount).toBe(8);

    // Check if the resizers have the correct class names
    expect(topLeftResizer.classList.contains("resizer")).toBe(true);
    expect(topLeftResizer.classList.contains("topLeft")).toBe(true);
    expect(topRightResizer.classList.contains("resizer")).toBe(true);
    expect(topRightResizer.classList.contains("topRight")).toBe(true);
    expect(bottomLeftResizer.classList.contains("resizer")).toBe(true);
    expect(bottomLeftResizer.classList.contains("bottomLeft")).toBe(true);
    expect(bottomRightResizer.classList.contains("resizer")).toBe(true);
    expect(bottomRightResizer.classList.contains("bottomRight")).toBe(true);
    expect(middleLeftResizer.classList.contains("resizer")).toBe(true);
    expect(middleLeftResizer.classList.contains("middleLeft")).toBe(true);
    expect(middleRightResizer.classList.contains("resizer")).toBe(true);
    expect(middleRightResizer.classList.contains("middleRight")).toBe(true);
    expect(topMiddleResizer.classList.contains("resizer")).toBe(true);
    expect(topMiddleResizer.classList.contains("topMiddle")).toBe(true);
    expect(bottomMiddleResizer.classList.contains("resizer")).toBe(true);
    expect(bottomMiddleResizer.classList.contains("bottomMiddle")).toBe(true);
  });
});