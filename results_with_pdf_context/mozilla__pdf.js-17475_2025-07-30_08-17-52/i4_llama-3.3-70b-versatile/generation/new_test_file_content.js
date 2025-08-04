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

  it("should make highlight visible when savingprinting a cropped pdf", async () => {
    const { getDocument } = await import('../../display/api.js');
    const { buildGetDocumentParams } = await import('./test_utils.js');
    const { PDFPageView } = await import('../../web/pdf_page_view.js');
    const { PDFViewer } = await import('../../web/pdf_viewer.js');
    const { Util } = await import('../../shared/util.js');
    const loadingTask = getDocument(buildGetDocumentParams('bug1872721.pdf'));
    const pdfViewer = new PDFViewer({
      container: document.createElement('div'),
      viewer: document.createElement('div'),
      renderInteractiveForms: false,
    });
    const pdfDoc = await loadingTask.promise;
    const pdfPage = await pdfDoc.getPage(1);
    const pageView = new PDFPageView({
      container: document.createElement('div'),
      id: 1,
      scale: 1,
      renderingQueue: pdfViewer.renderingQueue,
      viewport: pdfPage.getViewport({ scale: 1 }),
      useDocumentColors: false,
    });
    const annotationEditor = new (await import('./highlight.js')).HighlightEditor({
      annotation: {
        subtype: 'Highlight',
        rect: [10, 10, 50, 50],
        color: [1, 0, 0],
        opacity: 1,
      },
      pageIndex: 0,
      pageView: pageView,
    });
    const expectedQuadPoints = annotationEditor.serialize().quadPoints;
    const actualQuadPoints = annotationEditor.serialize().quadPoints;
    await pdfPage.render({
      canvasContext: null,
      viewport: pageView.viewport,
      renderInteractiveForms: false,
      annotationEditor,
    });
    const highlightEditor = new (await import('./highlight.js')).HighlightEditor({
      annotation: {
        subtype: 'Highlight',
        rect: [10, 10, 50, 50],
        color: [1, 0, 0],
        opacity: 1,
      },
      pageIndex: 0,
      pageView: pageView,
    });
    const rect = [10, 10, 50, 50];
    const quadPoints = highlightEditor.#serializeBoxes(rect);
    const expectedVisibility = true;
    const actualVisibility = quadPoints.some((point) => point > 0);
    expect(actualVisibility).toBe(expectedVisibility);
  });
});