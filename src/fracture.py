"""
Module for statistical description of the fracture networks.
It provides appropriate statistical models as well as practical sampling methods.
"""

from typing import Union, List
import numpy as np
import attr



@attr.s(auto_attribs=True)
class FractureShape:
    """
    Single fracture sample.
    """
    r: float
    # Size of the fracture, laying in XY plane
    centre: np.array
    # location of the barycentre of the fracture
    rotation_axis: np.array
    # axis of rotation
    rotation_angle: float
    # angle of rotation around the axis (?? counterclockwise with axis pointing up)
    region: Union[str, int]
    # name or ID of the physical group
    aspect: float = 1
    # aspect ratio of the fracture, y_length : x_length, x_length == r

    @property
    def rx(self):
        return self.r

    @property
    def ry(self):
        return self.r * self.aspect



class Quat:
    """
    Simple quaternion class as numerically more stable alternative to the Orientation methods.
    TODO: finish, test, substitute
    """
    def __init__(self, q):
        self.q = q

    def __matmul__(self, other: 'Quat') -> 'Quat':
        """
        Composition of rotations. Quaternion multiplication.
        """
        w1, x1, y1, z1 = self.q
        w2, x2, y2, z2 = other.q
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2
        z = w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2
        return Quat((w, x, y, z))


    @staticmethod
    def from_euler(a:float, b:float, c:float) -> 'Quat':
        """
        X-Y-Z Euler angles to quaternion
        :param a: angle to rotate around Z
        :param b: angle to rotate around X
        :param c: angle to rotate around Z
        :return: Quaterion for composed rotation.
        """
        return Quat([np.cos(a / 2), 0, 0,np.sin(a / 2)]) @ \
                Quat([np.cos(b / 2), 0, np.sin(b / 2), 0]) @\
                Quat([np.cos(c / 2), np.sin(c / 2), 0, 0])

    def axisangle_to_q(v, theta):
        # convert rotation given by axis 'v' and angle 'theta' to quaternion representation
        v = normalize(v)
        x, y, z = v
        theta /= 2
        w = cos(theta)
        x = x * sin(theta)
        y = y * sin(theta)
        z = z * sin(theta)
        return w, x, y, z

    def q_to_axisangle(q):
        # convert from quaternion to ratation given by axis and angle
        w, v = q[0], q[1:]
        theta = acos(w) * 2.0
        return normalize(v), theta


@attr.s(auto_attribs=True)
class FisherOrientation:
    """
    Distribution for random orientation in 3d.

    Coordinate system: X - east, Y - north, Z - up
    """

    trend: float
    # mean fracture normal, azimuth of its projection to the horizontal plane
    # related term is the strike =  trend - 90; that is azimuth of the strike line
    # - the intersection of the fracture with the horizontal plane
    plunge: float
    # mean fracture normal, angle between the normal and the horizontal plane
    # ralated term is the dip = 90 - plunge; that is the angle between the fracture and the horizontal plane
    #
    # strike and dip can by understood as the first two Eulerian angles.
    dispersion: float
    # the dispersion parameter; 0 = uniform dispersion, infty - no dispersion

    @staticmethod
    def strike_dip(strike, dip, dispersion):
        """
        Initialize from (strike, dip, concentration==dispersion)
        """
        return FisherOrientation(strike + 90, 90 - dip, dispersion)


    def _sample_standard_fisher(self, n) -> np.array:
        """
        Normal vector of random fractures with mean direction (0,0,1).
        :param n:
        :return: array of normals (n, 3)
        """
        if self.dispersion == np.inf:
            normals = np.zeros((n, 3))
            normals[:, 2] = 1.0
        else:
            unif = np.random.uniform(size=n)
            psi = 2 * np.pi * np.random.uniform(size=n)
            cos_psi = np.cos(psi)
            sin_psi = np.sin(psi)
            if self.dispersion == 0:
                cos_theta = 1 - 2 * unif
            else:
                exp_k = np.exp(self.dispersion)
                exp_ik = 1 / exp_k
                cos_theta = np.log(exp_k - unif * ( exp_k - exp_ik) ) / self.dispersion
            sin_theta = np.sqrt(1 - cos_theta**2)
            normals = np.stack((sin_psi * cos_theta, cos_psi * cos_theta, sin_theta), axis=1)
        return normals
        # rotate to mean strike and dip

    def sample_normal(self, size=1):
        """
        Draw samples for the fracture normals.
        :param size: number of samples
        :return: array (n, 3)
        """
        raw_normals = self._sample_standard_fisher(size)
        mean_norm = self._mean_normal()
        axis_angle = self.normal_to_axis_angle(mean_norm[None,:])
        return self.rotate(raw_normals, axis_angle = axis_angle[0])

    def sample_axis_angle(self, size=1):
        """
        Sample fracture orientation angles.
        :param size: Number of samples
        :return: shape (n, 4), every row: unit axis vector and angle
        """
        normals = self.sample_normal(size)
        return self.normal_to_axis_angle(normals[:])

    @staticmethod
    def normal_to_axis_angle(normals):
        z_axis = np.array([0, 0, 1], dtype=float)
        norms = normals / np.linalg.norm(normals, axis=1)[:, None]
        cos_angle = norms @ z_axis
        angles = np.arccos(cos_angle)
        # sin_angle = np.sqrt(1-cos_angle**2)

        axes = np.cross(z_axis, norms, axisb=1)
        ax_norm = np.maximum( np.linalg.norm(axes, axis=1), 1e-200)
        axes = axes / ax_norm[:, None]

        return np.concatenate([axes, angles[:, None]], axis=1)

    @staticmethod
    def rotate(vectors, axis=None, angle=0, axis_angle=None):
        """
        Rotate given vector around given 'axis' by the 'angle'.
        :param vectors: array of 3d vectors, shape (n, 3)
        :param axis_angle: pass both as array (4,)
        :return: shape (n, 3)
        """
        if axis_angle is not None:
            axis, angle = axis_angle[:3], axis_angle[3]
        if angle == 0:
            return vectors
        vectors = np.atleast_2d(vectors)
        cos_angle, sin_angle = np.cos(angle), np.sin(angle)

        rotated = vectors * cos_angle\
                  + np.cross(axis, vectors, axisb=1) * sin_angle\
                  + axis[None, :] * (vectors @ axis)[:, None] * (1 - cos_angle)
        # Rodrigues formula for rotation of vectors around axis by an angle
        return rotated

    def _mean_normal(self):
        trend = np.radians(self.trend)
        plunge = np.radians(self.plunge)

        normal = np.array( [np.sin(trend) * np.cos(plunge),
                            np.cos(trend) * np.cos(plunge),
                            np.sin(plunge)])

        #assert np.isclose(np.linalg.norm(normal), 1, atol=1e-15)
        return normal


    # def normal_2_trend_plunge(self, normal):
    #
    #     plunge = round(degrees(-np.arcsin(normal[2])))
    #     if normal[1] > 0:
    #         trend = round(degrees(np.arctan(normal[0] / normal[1]))) + 360
    #     else:
    #         trend = round(degrees(np.arctan(normal[0] / normal[1]))) + 270
    #
    #     if trend > 360:
    #         trend = trend - 360
    #
    #     assert trend == self.trend
    #     assert plunge == self.plunge


class Position:
    def __init__(self):


@attr.s(auto_attribs=True)
class PowerLawSize:
    """
    Truncated Power Law model for the fracture size distribution.
    density:

    f(r) = f_0 r ** (-power - 1)

    on [size_min, size_max], zero elsewhere.
    """
    power: float
    # power of th power law
    diam_range: (float, float)
    # lower and upper bound of the power law for the fracture diameter (size), values for which the intensity is given
    intensity: float
    # number of fractures with size in the size_range per unit volume, denoted also P30
    sample_range: (float, float)
    # range used for sampling., not part of the statistical description

    def _cdf(self, x, min, max):
        # Distribution function
        pmin = min ** (-self.power)
        pmax = max ** (-self.power)
        return (pmin - x ** (-self.power))/(pmin - pmax)


    def _ppf(self, x, min, max):
        # Quantile function
        pmin = min ** (-self.power)
        pmax = max ** (-self.power)
        scaled = pmin - x*(pmin - pmax)
        return scaled ** (-1 / self.power)

    def range_intensity(self, range):
        a, b = self.diam_range
        c, d = range
        k = self.power
        return self.intensity * (c**(-k) - d**(-k)) / (a**(-k) - b**(-k))

    def set_sample_range(self, sample_range=None):
        """
        Rescale to the new
        :param sample_range:
        :return:
        """
        if sample_range is None:
            sample_range = self.diam_range
        self._sample_range = sample_range
        self._sample_intensity = self.range_intensity(self._sample_range)

    def set_range_by_intensity(self, intensity):
        a, b = self.diam_range
        c, d = self.sample_range
        k = self.power
        self.sample_range[0] = (intensity * (a**(-k) - b**(-k)) / self.intensity + d**(-k)) ** (-1/k)

    def mean_size(self, volume):
        """
        :return: Mean of number of fractures.
        """
        return self._sample_intensity * volume


    def sample(self, volume, size=None):
        """
        Sample the fracture diameters.
        :return:
        """
        if size is None:
            size = np.random.poisson(lam=self.mean_size(volume), size=1)
        U = np.random.rand(size=size)
        return self._ppf(U, self._sample_range[0], self._sample_range[1])





# @attr.s(auto_attribs=True)
# class PoissonIntensity:
#     p32: float
#     # number of fractures
#     size_min: float
#     #
#     size_max:
#     def sample(self, box_min, box_max):


@attr.s(auto_attribs=True)
class FrFamily:
    name: str
    orientation: FisherOrientation
    shape: PowerLawSize


class Populatfion:
    """
    Data class to describe whole population of fractures, several families.
    """
    def __init__(self, volume):
        """
        :param orientation: Orientation stochastic model
        :param size: Size stochastic model.
        :param intenzity: Stochastic model.
        """
        self.volume = volume
        self.families = []


    @staticmethod
    def load(json_stream):
        """
        Load families from a JSON stream. Assuming fixed statistical model: Fischer, Uniform, PowerLaw Poisson
        :param json_stream:
        :return: Population instance.
        """


    def add_family(self, name, position, shape):
        self.families.append( FrFamily(name, position, shape) )


    def mean_size(self):
        return sum(( family.shape.mean_size(self.volume) for family in self.families))


    def set_sample_range(self, sample_range, max_sample_size=None):
        """
        Set sample range for fracture diameter.
        :param sample_range:
        :param max_sample_size: If provided, the lower bound is enlarged in order to achieve
        this limit on mean of the number of fractures.
        :return:
        """
        for f in self.families:
            f.shape.set_sample_range(sample_range)
        if max_sample_size is not None:
            total_size = self.mean_size()
            if total_size > max_sample_size:
                for f in self.families:
                    f.shape.set_range_by_intensity( f.mean_size(volume) / total_size * max_sample_size / self.volume)



    def sample(self):
        """
        Provide a single fracture sample from the population.
        :return:
        """
        fractures = []
        for f in self.families:
            name = f.name
            diams = f.shape.sample(self.volume)
            fr_axis_angle = f.orientation.sample_axis_angle(len(diams))
            centers = np.random.rand(len(diams), 3)
            for r, aa, c in zip(diams, fr_axis_angle, centers):
                axis, angle = aa[:3], aa[3]
                fractures.append(FractureShape(r, c, axis, angle, name, 1))
        return fractures
#
#
#
#
#
# class FractureGenerator:
#     def __init__(self, frac_type):
#         self.frac_type = frac_type
#
#     def generate_fractures(self, min_distance, min_radius, max_radius):
#         fractures = []
#
#         for i in range(self.frac_type.n_fractures):
#             x = uniform(2 * min_distance, 1 - 2 * min_distance)
#             y = uniform(2 * min_distance, 1 - 2 * min_distance)
#             z = uniform(2 * min_distance, 1 - 2 * min_distance)
#
#             tpl = TPL(self.frac_type.kappa, self.frac_type.r_min, self.frac_type.r_max, self.frac_type.r_0)
#             r = tpl.rnd_number()
#
#             orient = Orientation(self.frac_type.trend, self.frac_type.plunge, self.frac_type.k)
#             axis, angle = orient.compute_axis_angle()
#
#             fd = FractureData(x, y, z, r, axis[0], axis[1], axis[2], angle, i * 100)
#
#             fractures.append(fd)
#
#         return fractures
#
#     def write_fractures(self, fracture_data, file_name):
#         with open(file_name, "w") as writer:
#             for d in fracture_data:
#                 writer.write("%f %f %f %f %f %f %f %f %d\n" % (d.centre[0], d.centre[1], d.centre[2], d.r, d.rotation_axis[0],
#                                                         d.rotation_axis[1], d.rotation_axis[2], d.rotation_angle, d.tag))
#
#     def read_fractures(self, file_name):
#         data = []
#         with open(file_name, "r") as reader:
#             for l in reader.readlines():
#                 x, y, z, r, axis_0, axis_1, axis_2, angle = [float(i) for i in l.split(' ')[:-1]]
#                 tag = int(l.split(' ')[-1])
#                 d = FractureData(x, y, z, r, axis_0, axis_1, axis_2, angle, tag)
#                 data.append(d)
#
#         return data
#
#