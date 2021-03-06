#!/usr/bin/env python3

"""
Demo to show multiple shower images on a single figure using
`CameraDisplay` and really simple toymodel shower images (not
simulations). Also shows how to change the color palette.
"""

import matplotlib.pylab as plt
from astropy import units as u

from ctapipe.instrument import CameraGeometry
from ctapipe.visualization import CameraDisplay
from ctapipe.image import toymodel
from ctapipe.image import hillas_parameters
from ctapipe.image import tailcuts_clean


def draw_several_cams(geom, ncams=4):

    cmaps = ['jet', 'afmhot', 'terrain', 'autumn']
    fig, axs = plt.subplots(1, ncams, figsize=(15, 4), sharey=True, sharex=True)

    for ii in range(ncams):
        disp = CameraDisplay(
            geom,
            ax=axs[ii],
            title="CT{}".format(ii + 1),
        )
        disp.cmap = cmaps[ii]

        model = toymodel.generate_2d_shower_model(
            centroid=(0.2 - ii * 0.1, -ii * 0.05),
            width=0.005 + 0.001 * ii,
            length=0.1 + 0.05 * ii,
            psi=ii * 20 * u.deg,
        )

        image, sig, bg = toymodel.make_toymodel_shower_image(
            geom,
            model.pdf,
            intensity=50,
            nsb_level_pe=1000,
        )

        mask = tailcuts_clean(geom, image, picture_thresh=6*image.mean(),
                              boundary_thresh=4*image.mean())
        cleaned = image.copy()
        cleaned[~mask] = 0

        hillas = hillas_parameters(geom, cleaned)

        disp.image = image
        disp.add_colorbar(ax=axs[ii])

        disp.set_limits_percent(95)
        disp.overlay_moments(hillas, linewidth=3, color='blue')


if __name__ == '__main__':

    hexgeom = CameraGeometry.from_name("LSTCam")
    recgeom = CameraGeometry.make_rectangular()

    draw_several_cams(recgeom)
    draw_several_cams(hexgeom)

    plt.tight_layout()
    plt.show()
