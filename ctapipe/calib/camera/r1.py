"""
Calibrator for the R0 -> R1 data level transition.

This module handles the calibration from the R0 data level to R1. This data
level transition will be handled by the camera servers, not in the pipeline,
however the pipeline can be used as a test-bench in the comissioning stage of
the cameras.

As the R1 calibration is camera specific, each camera (and seperately the MC)
requires their own calibrator class with inherits from `CameraR1Calibrator`.
`HessioR1Calibrator` is the calibrator for the MC data obtained from readhess.
Through the use of `CameraR1CalibratorFactory`, the correct
`CameraR1Calibrator` can be obtained based on the origin (MC/Camera format)
of the data.
"""
from traitlets import CaselessStrEnum, Unicode
from ctapipe.core import Component, Factory
from abc import abstractmethod

__all__ = ['HessioR1Calibrator', 'CameraR1CalibratorFactory']

CALIB_SCALE = 1.05
"""
CALIB_SCALE is only relevant for MC calibration.

CALIB_SCALE is the factor needed to transform from mean p.e. units to units of
the single-p.e. peak: Depends on the collection efficiency, the asymmetry of
the single p.e. amplitude  distribution and the electronic noise added to the
signals. Default value is for GCT.

To correctly calibrate to number of photoelectron, a fresh SPE calibration
should be applied using a SPE sim_telarray run with an artificial light source.
"""


class CameraR1Calibrator(Component):
    """
    The base R1-level calibrator. Fills the r1 container.

    The R1 calibrator performs the camera-specific R1 calibration that is
    usually performed on the raw data by the camera server. This calibrator
    exists in ctapipe for testing and prototyping purposes.

    Parameters
    ----------
    config : traitlets.loader.Config
        Configuration specified by config file or cmdline arguments.
        Used to set traitlet values.
        Set to None if no configuration to pass.
    tool : ctapipe.core.Tool or None
        Tool executable that is calling this component.
        Passes the correct logger to the component.
        Set to None if no Tool to pass.
    kwargs
    """

    name = 'CameraR1Calibrator'
    origin = None

    def __init__(self, config, tool, **kwargs):
        """
        Parent class for the r1 calibrators. Fills the r1 container.

        Parameters
        ----------
        config : traitlets.loader.Config
            Configuration specified by config file or cmdline arguments.
            Used to set traitlet values.
            Set to None if no configuration to pass.
        tool : ctapipe.core.Tool or None
            Tool executable that is calling this component.
            Passes the correct logger to the component.
            Set to None if no Tool to pass.
        kwargs
        """
        super().__init__(config=config, parent=tool, **kwargs)
        if self.origin is None:
            raise ValueError("Subclass of CameraR1Calibrator should specify "
                             "an origin")

        self._r0_empty_warn = False

    @abstractmethod
    def calibrate(self, event):
        """
        Abstract method to be defined in child class.

        Perform the conversion from raw R0 data to R1 data
        (ADC Samples -> PE Samples), and fill the r1 container.

        Parameters
        ----------
        event : container
            A `ctapipe` event container
        """

    def check_r0_exists(self, event, telid):
        """
        Check that r0 data exists. If it does not, then do not change r1.

        This ensures that if the containers were filled from a file containing
        r0 data, it is not overwritten by non-existant data.

        Parameters
        ----------
        event : container
            A `ctapipe` event container
        telid : int
            The telescope id.

        Returns
        -------
        bool
            True if r0.tel[telid].adc_samples is not None, else false.
        """
        r0 = event.r0.tel[telid].adc_samples
        if r0 is not None:
            return True
        else:
            if not self._r0_empty_warn:
                self.log.warning("Encountered an event with no R0 data. "
                                 "R1 is unchanged in this circumstance.")
                self._r0_empty_warn = True
            return False


class HessioR1Calibrator(CameraR1Calibrator):
    """
    The R1 calibrator for hessio files. Fills the r1 container.

    This calibrator correctly applies the pedestal subtraction and conversion
    from counts to photoelectrons for the Monte-Carlo data.

    Parameters
    ----------
    config : traitlets.loader.Config
        Configuration specified by config file or cmdline arguments.
        Used to set traitlet values.
        Set to None if no configuration to pass.
    tool : ctapipe.core.Tool or None
        Tool executable that is calling this component.
        Passes the correct logger to the component.
        Set to None if no Tool to pass.
    kwargs
    """

    name = 'HessioR1Calibrator'
    origin = 'hessio'

    def calibrate(self, event):
        if event.meta['origin'] != 'hessio':
            raise ValueError('Using HessioR1Calibrator to calibrate a '
                             'non-hessio event.')

        for telid in event.r0.tels_with_data:
            if self.check_r0_exists(event, telid):
                samples = event.r0.tel[telid].adc_samples
                n_samples = samples.shape[2]
                ped = event.mc.tel[telid].pedestal / n_samples
                gain = event.mc.tel[telid].dc_to_pe * CALIB_SCALE
                calibrated = (samples - ped[..., None]) * gain[..., None]
                event.r1.tel[telid].pe_samples = calibrated


# External Children
try:
    from targetpipe.calib.camera.r1 import TargetioR1Calibrator
except ImportError:
    pass


class CameraR1CalibratorFactory(Factory):
    """
    The R1 calibrator `ctapipe.core.factory.Factory`. This
    `ctapipe.core.factory.Factory` allows the correct
    `CameraR1Calibrator` to be obtained for the data investigated. The
    discriminator used by this factory is the "origin" of the file, a string
    obtainable from `ctapipe.io.eventfilereader.EventFileReader.origin`.

    Additional filepaths are required by some cameras for R1 calibration. Due
    to the current inplementation of `ctapipe.core.factory.Factory`, every
    trait that could
    possibly be required for a child `ctapipe.core.component.Component` of
    `CameraR1Calibrator` must
    be included in this `ctapipe.core.factory.Factory`. The
    `CameraR1Calibrator` specific to a
    camera type should then define how/if that filepath should be used. The
    format of the file is not restricted, and the file can be read from inside
    ctapipe, or can call a different library created by the camera teams for
    the calibration of their camera.

    Parameters
    ----------
    config : traitlets.loader.Config
        Configuration specified by config file or cmdline arguments.
        Used to set traitlet values.
        Set to None if no configuration to pass.
    tool : ctapipe.core.Tool or None
        Tool executable that is calling this component.
        Passes the correct logger to the component.
        Set to None if no Tool to pass.
    kwargs

    Attributes
    ----------
    origin : traitlets.CaselessStrEnum
        A string describing the origin of the event file being calibrated.
        Should be obtained from the
        `ctapipe.io.eventfilereader.EventFileReader.origin` attribute of the
        correct `ctapipe.io.eventfilereader.EventFileReader` for the file.
    pedestal_path : traitlets.Unicode
        A string containing the path to a file containing the electronic
        pedestal to be subtracted from the waveforms. How/if this file is used
        is defined by the `CameraR1Calibrator` specific to the camera.
    tf_path : traitlets.Unicode
        A string containing the path to a file containing the transfer
        function to be applied to the waveforms to fix the non-linearity of
        the digitiser. How/if this file is used is defined by the
        `CameraR1Calibrator` specific to the camera.
    pe_path : traitlets.Unicode
        A string containing the path to a file containing the conversion
        coefficients into photoelectrons. How/if this file is used is defined
        by the `CameraR1Calibrator` specific to the camera.
    ff_path : traitlets.Unicode
        A string containing the path to a file containing the flat-field
        conversion coefficients. How/if this file is used is defined by the
        `CameraR1Calibrator` specific to the camera.
    """

    name = "CameraR1CalibratorFactory"
    description = "Obtain CameraR1Calibrator based on file origin"

    subclasses = Factory.child_subclasses(CameraR1Calibrator)
    subclass_names = [c.origin for c in subclasses]

    origin = CaselessStrEnum(subclass_names, 'hessio',
                             help='Origin of events to be '
                                  'calibration.').tag(config=True)

    # Product classes traits
    pedestal_path = Unicode('', allow_none=True,
                            help='Path to a pedestal file').tag(config=True)
    tf_path = Unicode('', allow_none=True,
                      help='Path to a Transfer Function file').tag(config=True)
    pe_path = Unicode('', allow_none=True,
                          help='Path to an pe conversion file').tag(config=True)
    ff_path = Unicode('', allow_none=True,
                      help='Path to a flat field file').tag(config=True)

    def get_factory_name(self):
        return self.name

    def get_product_name(self):
        return self.origin
