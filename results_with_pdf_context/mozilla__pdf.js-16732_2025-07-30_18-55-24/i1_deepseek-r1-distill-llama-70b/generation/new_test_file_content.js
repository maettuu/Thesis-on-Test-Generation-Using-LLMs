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

  it("should change mouse cursor when hovering over different resizer edges", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { AnnotationEditorParamsType } = await import("../../shared/util.js");

    const parent = {
      pageDimensions: [100, 100],
      viewport: {
        rawDims: { pageWidth: 100, pageHeight: 100, pageX: 0, pageY: 0 },
        rotation: 0,
      },
    };

    const editor = new AnnotationEditor({
      parent,
      id: "testEditor",
      uiManager: {},
      name: "testEditor",
    });

    editor._willKeepAspectRatio = true;
    editor.makeResizable();

    const resizers = editor.#resizersDiv.children;
    const resizerPositions = ["topLeft", "topRight", "bottomRight", "bottomLeft"];

    expect(editor.#resizersDiv?.children).toHaveLength(8);

    for (const resizer of resizers) {
      const position = resizer.classList[1];
      if (position === "topLeft" || position === "bottomRight") {
        expect(resizer.dataset.cursor).toBe("nwse-resize");
      } else if (position === "topRight" || position === "bottomLeft") {
        expect(resizer.dataset.cursor).toBe("nesw-resize");
      } else if (position === "topMiddle") {
        expect(resizer.dataset.cursor).toBe("n-resize");
      } else if (position === "middleRight") {
        expect(resizer.dataset.cursor).toBe("e-resize");
      } else if (position === "bottomMiddle") {
        expect(resizer.dataset.cursor).toBe("s-resize");
      } else if (position === "middleLeft") {
        expect(resizer.dataset.cursor).toBe("w-resize");
      }
    }
  });
});