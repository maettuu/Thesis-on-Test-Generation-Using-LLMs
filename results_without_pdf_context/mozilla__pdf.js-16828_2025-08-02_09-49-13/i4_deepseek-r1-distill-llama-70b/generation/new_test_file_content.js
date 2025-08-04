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

  it("should create a StampEditor when pasting an image from clipboard", async () => {
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");
    const { StampEditor } = await import("../../display/editor/stamp.js");

    const container = {
      focus: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    };

    const mockViewer = {};
    const mockEventBus = {
      _on: jest.fn(),
      _off: jest.fn(),
      dispatch: jest.fn(),
    };
    const mockPdfDocument = {};
    const mockPageColors = {};

    const uiManager = new AnnotationEditorUIManager(
      container,
      mockViewer,
      mockEventBus,
      mockPdfDocument,
      mockPageColors
    );

    const mockClipboardEvent = {
      clipboardData: {
        getData: () => "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
      },
      preventDefault: jest.fn(),
    };

    // Before patch: should not create StampEditor
    const beforePatchResult = await import("../../display/editor/tools.js");
    expect(beforePatchResult.AnnotationEditorUIManager.paste(mockClipboardEvent)).not.toCreate(StampEditor);

    // After patch: should create StampEditor
    const afterPatchResult = await import("../../display/editor/tools.js");
    await afterPatchResult.AnnotationEditorUIManager.paste(mockClipboardEvent);
    expect(afterPatchResult.AnnotationEditorLayer.createEditor).toHaveBeenCalled();
  });
});