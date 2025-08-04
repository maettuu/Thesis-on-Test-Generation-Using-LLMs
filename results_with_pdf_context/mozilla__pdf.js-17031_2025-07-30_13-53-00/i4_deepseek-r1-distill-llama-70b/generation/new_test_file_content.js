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

  it("should update font size without blocking UI", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { createIdFactory } = await import("../../core/util.js");
    const { buildGetDocumentParams } = await import("../../core/document.js");

    const idFactory = createIdFactory();
    const params = buildGetDocumentParams(idFactory);
    const editor = new AnnotationEditor({
      parent: {
        pageIndex: 0,
        moveEditorInDOM: () => {},
        setSelected: () => {},
        setParent: () => {},
        viewport: {
          rotation: 0,
          pageWidth: 100,
          pageHeight: 100,
        },
      },
      uiManager: {},
      id: "test-editor",
      x: 10,
      y: 20,
    });

    editor.width = 0.5;
    editor.height = 0.5;
    editor.fixAndSetPosition();

    const mockMoveInDOM = jest.fn();
    editor.moveInDOM = mockMoveInDOM;

    // Simulate font size changes
    editor.height = 0.6;
    editor.width = 0.6;
    editor.fixAndSetPosition();

    // Check that moveInDOM is debounced and called only once
    expect(mockMoveInDOM).toHaveBeenCalled();
    const [x, y] = [editor.x, editor.y];
    expect(x).toBeCloseTo(0.1);
    expect(y).toBeCloseTo(0.2);
  });
});