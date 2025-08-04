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

  it("should change the mouse cursor state according to the edge we resize it from for added images and drawings in PDF documents", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { PDFDocument } = await import("../../core/document.js");
    const { PDFPage } = await import("../../core/document.js");
    const { PDFViewer } = await import("../../web/pdf_viewer.js");

    const pdfDocument = await PDFDocument.load(await fetch("example.pdf").then(response => response.arrayBuffer()));
    const pdfPage = pdfDocument.getPage(1);
    const pdfViewer = new PDFViewer();
    const annotationEditorUIManager = new AnnotationEditorUIManager(pdfViewer);
    const annotationEditor = new AnnotationEditor({ uiManager: annotationEditorUIManager });

    annotationEditorUIManager.addEditor(annotationEditor);
    annotationEditor.makeResizable();

    const resizerDiv = annotationEditor.#resizersDiv;
    const resizerElements = resizerDiv.children;

    const expectedCursorStyles = {
      "topLeft": "nwse-resize",
      "topMiddle": "ns-resize",
      "topRight": "nesw-resize",
      "middleRight": "ew-resize",
      "bottomRight": "nwse-resize",
      "bottomMiddle": "ns-resize",
      "bottomLeft": "nesw-resize",
      "middleLeft": "ew-resize",
    };

    for (const resizerElement of resizerElements) {
      const className = resizerElement.classList[1];
      const expectedCursorStyle = expectedCursorStyles[className];

      resizerElement.dispatchEvent(new MouseEvent("pointerover", { bubbles: true }));
      const actualCursorStyle = globalThis.getComputedStyle(resizerElement).cursor;

      if (actualCursorStyle !== expectedCursorStyle) {
        throw new Error(`Expected cursor style '${expectedCursorStyle}' but got '${actualCursorStyle}' for resizer '${className}'`);
      }
    }
  });
});