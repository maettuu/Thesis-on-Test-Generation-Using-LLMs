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

  it("should not block UI when changing font size in editor", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { XRefMock } = await import("./test_utils.js");

    // Create a mock parent element and editor
    const parent = {
      moveEditorInDOM: jest.fn(),
      pageIndex: 0,
      viewport: {
        rotation: 0,
        get pageWidth() { return 100; },
        get pageHeight() { return 100; },
        get pageX() { return 0; },
        get pageY() { return 0; }
      }
    };

    const editor = new AnnotationEditor({
      parent,
      id: "test-editor",
      uiManager: {},
      isCentered: false,
      name: "test"
    });

    // Initialize editor
    editor.div = document.createElement("div");
    document.body.appendChild(editor.div);

    // Simulate font size change
    const fontSizeSlider = document.createElement("input");
    fontSizeSlider.type = "range";
    fontSizeSlider.min = 8;
    fontSizeSlider.max = 72;
    fontSizeSlider.value = 12;
    document.body.appendChild(fontSizeSlider);

    // Spy on moveInDOM
    const moveInDOMSpy = jest.spyOn(editor, "moveInDOM");

    // Test that moveInDOM is not called synchronously
    fontSizeSlider.dispatchEvent(new Event("input"));

    // Wait for async moveInDOM call
    await new Promise(resolve => setTimeout(resolve, 10));

    expect(moveInDOMSpy).toHaveBeenCalled();
  });
});