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

  it("should support pasting an image from the clipboard in editing mode", async () => {
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");
    const { StampEditor } = await import("../../display/editor/stamp.js");
    const { AnnotationEditorType } = await import("../../shared/util.js");

    const uiManager = new AnnotationEditorUIManager(null, null, null, { annotationStorage: {}, filterFactory: {} }, null);
    const layer = new AnnotationEditorLayer({
      uiManager,
      pageIndex: 0,
      div: document.createElement("div"),
      accessibilityManager: null,
      annotationLayer: null,
      viewport: { rotation: 0, rawDims: { pageWidth: 100, pageHeight: 100, pageX: 0, pageY: 0 } },
      l10n: null,
    });

    uiManager.addLayer(layer);
    uiManager.updateMode(AnnotationEditorType.STAMP);

    const clipboardEvent = new ClipboardEvent("paste", {
      clipboardData: new DataTransfer(),
    });
    clipboardEvent.clipboardData.items.add(new File([""], "image.png", { type: "image/png" }));

    uiManager.paste(clipboardEvent);

    const editors = Array.from(layer.#editors.values());
    expect(editors.length).toBe(1);
    expect(editors[0] instanceof StampEditor).toBe(true);
  });
});