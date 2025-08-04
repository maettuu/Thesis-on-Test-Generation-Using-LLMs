#test/unit/pdf_spec.js
/* Copyright 2023 Mozilla Foundation
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

import {
  AbortException,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationMode,
  CMapCompressionType,
  createValidAbsoluteUrl,
  FeatureTest,
  ImageKind,
  InvalidPDFException,
  isNodeJS,
  MissingPDFException,
  normalizeUnicode,
  OPS,
  PasswordResponses,
  PermissionFlag,
  PromiseCapability,
  shadow,
  UnexpectedResponseException,
  Util,
  VerbosityLevel,
} from "../../src/shared/util.js";
import {
  build,
  getDocument,
  PDFDataRangeTransport,
  PDFWorker,
  version,
} from "../../src/display/api.js";
import {
  DOMSVGFactory,
  fetchData,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  isDataScheme,
  isPdfFile,
  noContextMenu,
  PDFDateString,
  PixelsPerInch,
  RenderingCancelledException,
  setLayerDimensions,
} from "../../src/display/display_utils.js";
import {
  renderTextLayer,
  updateTextLayer,
} from "../../src/display/text_layer.js";
import { AnnotationEditorLayer } from "../../src/display/editor/annotation_editor_layer.js";
import { AnnotationEditorUIManager } from "../../src/display/editor/tools.js";
import { AnnotationLayer } from "../../src/display/annotation_layer.js";
import { ColorPicker } from "../../src/display/editor/color_picker.js";
import { DrawLayer } from "../../src/display/draw_layer.js";
import { GlobalWorkerOptions } from "../../src/display/worker_options.js";
import { Outliner } from "../../src/display/editor/outliner.js";
import { XfaLayer } from "../../src/display/xfa_layer.js";

const expectedAPI = Object.freeze({
  AbortException,
  AnnotationEditorLayer,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationEditorUIManager,
  AnnotationLayer,
  AnnotationMode,
  build,
  CMapCompressionType,
  ColorPicker,
  createValidAbsoluteUrl,
  DOMSVGFactory,
  DrawLayer,
  FeatureTest,
  fetchData,
  getDocument,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  GlobalWorkerOptions,
  ImageKind,
  InvalidPDFException,
  isDataScheme,
  isPdfFile,
  MissingPDFException,
  noContextMenu,
  normalizeUnicode,
  OPS,
  Outliner,
  PasswordResponses,
  PDFDataRangeTransport,
  PDFDateString,
  PDFWorker,
  PermissionFlag,
  PixelsPerInch,
  PromiseCapability,
  RenderingCancelledException,
  renderTextLayer,
  setLayerDimensions,
  shadow,
  UnexpectedResponseException,
  updateTextLayer,
  Util,
  VerbosityLevel,
  version,
  XfaLayer,
});

describe("pdfjs_api", function () {
  it("checks that the *official* PDF.js API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfjsAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.js"
        : "../../src/pdf.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfjsAPI }).toEqual(expectedAPI);
  });
});

describe("web_pdfjsLib", function () {
  it("checks that the viewer re-exports the expected API functionality", async function () {
    if (isNodeJS) {
      pending("loadScript is not supported in Node.js.");
    }
    const apiPath = "../../build/generic/build/pdf.mjs";
    await import(apiPath);

    const webPdfjsLib = await import("../../web/pdfjs.js");

    expect(Object.keys(webPdfjsLib).sort()).toEqual(
      Object.keys(expectedAPI).sort()
    );
  });

  it("should have accessible highlighted text for screen readers", async () => {
    const { PDFDocument } = await import("../../display/api.js");
    const { PDFPage } = await import("../../display/display_utils.js");
    const { TextLayer } = await import("../../display/text_layer.js");
    const { HighlightEditor } = await import("../../display/editor/highlight.js");

    // Create a simple PDF with a page containing text
    const pdf = new PDFDocument({
      content: [
        "1 0 0 1 0 0 cm",
        "/F1 12 Tf",
        "(Hello World!) Tj",
        "ET",
      ],
    });

    const page = new PDFPage(pdf, 0);
    const textLayer = new TextLayer({
      pageIndex: 0,
      container: document.createElement("div"),
    });

    // Render the text layer
    await textLayer.render();

    // Create a selection for the highlighted text
    const selection = document.getSelection();
    selection.removeRange(selection.getRangeAt(0));
    const range = document.createRange();
    range.selectNodeContents(textLayer.div);
    selection.addRange(range);

    // Create the highlight editor
    const highlightEditor = new HighlightEditor({
      anchorNode: range.startContainer,
      anchorOffset: 0,
      focusNode: range.endContainer,
      focusOffset: range.endOffset,
      boxes: [],
      methodOfCreation: "keyboard",
      text: "Hello World!",
    });

    // Render the highlight editor
    const highlightDiv = highlightEditor.render();

    // Check for the accessible text element
    const markElement = highlightDiv.querySelector("mark.visuallyHidden");
    expect(markElement).toBeTruthy();
    expect(markElement.textContent).toBe("Hello World!");
  });
});