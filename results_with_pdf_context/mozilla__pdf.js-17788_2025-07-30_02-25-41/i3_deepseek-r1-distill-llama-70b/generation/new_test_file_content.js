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

  it("should expose highlighted text to screen readers", async () => {
    const { getDocument } = await import("../../display/api.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { Util } = await import("../../shared/util.js");

    const pdfData = new TextEncoder().encode(
      "%PDF-1.3\n" +
      "1 0 obj\n" +
      "<</Type /Catalog /Pages 2 0 R>>\n" +
      "2 0 obj\n" +
      "<</Type /Pages /Kids [3 0 R] /Count 1 /Resources 4 0 R>>\n" +
      "3 0 obj\n" +
      "<</Type /Page /Parent 2 0 R /Resources 4 0 R /Contents 5 0 R>>\n" +
      "4 0 obj\n" +
      "<</ProcSet [/PDF /Text]>>\n" +
      "5 0 obj\n" +
      "<</Length 6 0 R>>\n" +
      "6 0 obj\n" +
      new TextEncoder().encode("BT\n/F1 24 Tf\n120 600 Td\n(Hello World!) Tj\nET\n") +
      "\n";

    const pdfBlob = new Blob([pdfData], { type: "application/pdf" });
    const pdfUrl = URL.createObjectURL(pdfBlob);

    const pdf = await getDocument({
      data: pdfBlob,
      url: pdfUrl,
      CMapLoader: null,
    });

    const container = document.createElement("div");
    document.body.appendChild(container);

    const editorUI = new AnnotationEditorUIManager(
      container,
      null,
      null,
      null,
      pdf,
      null,
      null,
      null
    );

    const annotationLayer = new AnnotationLayer();
    container.appendChild(annotationLayer.render());

    const page = pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1 });

    const textLayer = document.createElement("div");
    textLayer.className = "textLayer";
    textLayer.style.width = `${viewport.width}px`;
    textLayer.style.height = `${viewport.height}px`;
    container.appendChild(textLayer);

    await pdf.load();

    // Simulate text selection
    const selection = window.getSelection();
    const range = document.createRange();
    const textNode = document.createTextNode("Hello World!");
    textLayer.appendChild(textNode);
    range.selectNodeContents(textNode);
    selection.removeAllRanges();
    selection.addRange(range);

    editorUI.highlightSelection("main_toolbar");

    // Check that the highlighted text is exposed in the DOM
    const highlightDiv = textLayer.querySelector("mark.visuallyHidden");
    expect(highlightDiv).toBeTruthy();

    const expectedText = "Hello World!";
    expect(highlightDiv?.textContent).toBe(expectedText);
  });
});