# Guide to Image Coordinates (0-1000 Scale)

## 1. The Rule: 0 to 1000
Your code converts the input like this: `(Input / 1000) * 100`.
This means your input numbers must be between **0 and 1000**.

*   **0** = 0% (The very edge)
*   **500** = 50% (The exact center)
*   **1000** = 100% (The opposite edge)

## 2. The Map
Imagine your image is a square grid from 0 to 1000.

```text
      (0,0)  ---------------------->  (1000, 0)
        |  [ TOP-LEFT CORNER ]
        |
        |      (500, 500)
        |      [ CENTER POINT ]
        |
        v
   (0, 1000)  ----------------->  (1000, 1000)
```

| Position | X Value | Y Value |
| :--- | :--- | :--- |
| **Top-Left** | `0` | `0` |
| **Top-Right** | `1000` | `0` |
| **Center** | `500` | `500` |
| **Bottom-Left** | `0` | `1000` |
| **Bottom-Right** | `1000` | `1000` |

## 3. How to Calculate from Pixels
If you have the pixel coordinates from an image editor (e.g., Photoshop) and need to convert them to this 0-1000 scale:

**Formula:**
`(Pixel Coordinate ÷ Total Image Size) × 1000`

**Example:**
*   Your image is **2000 pixels wide**.
*   You want to target an object at **1500 pixels** from the left.
*   Math: `(1500 ÷ 2000) × 1000` = **750**.
*   **Your X coordinate is `750`.**

## 4. Summary Checklist
1.  **Order:** Always `X,Y` (Horizontal, then Vertical).
2.  **Range:** Keep numbers between `0` and `1000`.
3.  **Center:** Use `500,500` for the middle.
4.  **Origin:** `0,0` is Top-Left.