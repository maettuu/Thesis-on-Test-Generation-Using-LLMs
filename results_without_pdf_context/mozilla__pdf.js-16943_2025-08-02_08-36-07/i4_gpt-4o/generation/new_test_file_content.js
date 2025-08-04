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

  it("should change the style of the line and the resizers around a selected editor", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { FreeTextEditor } = await import("../../display/editor/freetext.js");
    const { InkEditor } = await import("../../display/editor/ink.js");

    const mockParent = {
      pageIndex: 0,
      viewport: {
        rotation: 0,
        rawDims: { pageWidth: 100, pageHeight: 100, pageX: 0, pageY: 0 },
      },
      div: document.createElement("div"),
      add: jest.fn(),
      remove: jest.fn(),
      setSelected: jest.fn(),
      toggleSelected: jest.fn(),
      setActiveEditor: jest.fn(),
      updateToolbar: jest.fn(),
      setEditingState: jest.fn(),
      isMultipleSelection: false,
    };

    const mockUIManager = {
      addToAnnotationStorage: jest.fn(),
      removeEditor: jest.fn(),
      isSelected: jest.fn().mockReturnValue(true),
      setUpDragSession: jest.fn(),
      endDragSession: jest.fn().mockReturnValue(false),
      dragSelectedEditors: jest.fn(),
      translateSelectedEditors: jest.fn(),
      currentLayer: { div: document.createElement("div") },
    };

    const editorParams = {
      parent: mockParent,
      uiManager: mockUIManager,
      id: "test-editor",
      x: 10,
      y: 10,
    };

    const freeTextEditor = new FreeTextEditor(editorParams);
    const inkEditor = new InkEditor(editorParams);

    document.body.appendChild(mockParent.div);
    mockParent.div.appendChild(freeTextEditor.render());
    mockParent.div.appendChild(inkEditor.render());

    freeTextEditor.select();
    inkEditor.select();

    const freeTextEditorStyle = getComputedStyle(freeTextEditor.div);
    const inkEditorStyle = getComputedStyle(inkEditor.div);

    const expectedBorderWidth = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--outline-width")) || 0;

    expect(freeTextEditorStyle.borderWidth).toBe(`${expectedBorderWidth}px`);
    expect(inkEditorStyle.borderWidth).toBe(`${expectedBorderWidth}px`);
  });
});