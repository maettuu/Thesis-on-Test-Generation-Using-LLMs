#test/unit/pdf.image_decoders_spec.js
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
  getVerbosityLevel,
  setVerbosityLevel,
  VerbosityLevel,
} from "../../src/shared/util.js";
import { Jbig2Error, Jbig2Image } from "../../src/core/jbig2.js";
import { JpegError, JpegImage } from "../../src/core/jpg.js";
import { JpxError, JpxImage } from "../../src/core/jpx.js";

describe("pdfimage_api", function () {
  it("checks that the *official* PDF.js-image decoders API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfimageAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.image_decoders.js"
        : "../../src/pdf.image_decoders.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfimageAPI }).toEqual({
      getVerbosityLevel,
      Jbig2Error,
      Jbig2Image,
      JpegError,
      JpegImage,
      JpxError,
      JpxImage,
      setVerbosityLevel,
      VerbosityLevel,
    });
  });

  it("should ignore EXIF orientation by replacing EXIF block data", async () => {
    const { JpegImage } = await import("../../core/jpg.js");
    // Construct a minimal JPEG file:
    // SOI (2 bytes) + APP1 marker (2 bytes) + APP1 length (2 bytes) + APP1 data (14 bytes) +
    // SOF0 marker (2 bytes) + SOF0 length (2 bytes) + SOF0 block (15 bytes) + EOI (2 bytes) = 41 bytes.
    const jpegData = new Uint8Array(41);
    let offset = 0;
    // SOI
    jpegData[offset++] = 0xff;
    jpegData[offset++] = 0xd8;
    // APP1 marker (0xffe1)
    jpegData[offset++] = 0xff;
    jpegData[offset++] = 0xe1;
    // APP1 block length: 0x0010 (16) => 14 bytes of data follow.
    jpegData[offset++] = 0x00;
    jpegData[offset++] = 0x10;
    // APP1 data: "Exif\0\0" followed by 8 non-zero bytes.
    jpegData[offset++] = 0x45; // E
    jpegData[offset++] = 0x78; // x
    jpegData[offset++] = 0x69; // i
    jpegData[offset++] = 0x66; // f
    jpegData[offset++] = 0x00;
    jpegData[offset++] = 0x00;
    jpegData[offset++] = 0x01;
    jpegData[offset++] = 0x02;
    jpegData[offset++] = 0x03;
    jpegData[offset++] = 0x04;
    jpegData[offset++] = 0x05;
    jpegData[offset++] = 0x06;
    jpegData[offset++] = 0x07;
    jpegData[offset++] = 0x08;
    // SOF0 marker (0xffc0)
    jpegData[offset++] = 0xff;
    jpegData[offset++] = 0xc0;
    // SOF0 block length: 0x0011 (17) -> 15 bytes follow.
    jpegData[offset++] = 0x00;
    jpegData[offset++] = 0x11;
    // SOF0 block: precision, height, width, numComponents, and dummy component specs.
    jpegData[offset++] = 0x08; // precision
    jpegData[offset++] = 0x00; jpegData[offset++] = 0x10; // height = 16
    jpegData[offset++] = 0x00; jpegData[offset++] = 0x10; // width = 16
    jpegData[offset++] = 0x03; // numComponents = 3
    // Component 1
    jpegData[offset++] = 0x01; jpegData[offset++] = 0x11; jpegData[offset++] = 0x00;
    // Component 2
    jpegData[offset++] = 0x02; jpegData[offset++] = 0x11; jpegData[offset++] = 0x00;
    // Component 3
    jpegData[offset++] = 0x03; jpegData[offset++] = 0x11; jpegData[offset++] = 0x00;
    // EOI marker
    jpegData[offset++] = 0xff;
    jpegData[offset++] = 0xd9;
    // Process the JPEG data.
    const result = JpegImage.canUseImageDecoder(jpegData);
    if (!result) {
      throw new Error("JPEG image not usable.");
    }
    // The APP1 data starts at offset 6 and is 14 bytes long.
    // The first 6 bytes ("Exif\0\0") should remain intact.
    const expectedHeader = [0x45, 0x78, 0x69, 0x66, 0x00, 0x00];
    for (let i = 0; i < 6; i++) {
      if (jpegData[6 + i] !== expectedHeader[i]) {
        throw new Error("APP1 header modified incorrectly");
      }
    }
    // The remaining 8 bytes should have been replaced with zeros.
    for (let i = 6; i < 14; i++) {
      if (jpegData[6 + i] !== 0x00) {
        throw new Error("APP1 data not cleared as expected");
      }
    }
  });
});