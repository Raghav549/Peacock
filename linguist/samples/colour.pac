// Perceptual colour: conversion, contrast and mixing.
module colour_sample

use colour

fn main() -> Unit {
    let violet = colour.oklch(0.62, 0.19, 300.0);
    let teal = colour.srgb(0.05, 0.55, 0.55);
    print("violet: " + colour.to_css(violet));
    print("contrast: " + str(colour.contrast(violet, teal)));
    print("mixed: " + colour.to_css(colour.mix(violet, teal, 0.5)));
    print("lightened: " + colour.to_css(colour.lighten(violet, 0.2)));
}
