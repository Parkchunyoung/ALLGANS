from model.AbstractGANModel import AbstractGANModel
from util.SequenceModel import SequenceModel
from util.ops import *
from util.summary_func import summary_variable, summary_image
from dict_keys.dataset_batch_keys import *
import numpy as np


class WGAN_GP(AbstractGANModel):
    VERSION = 1.0
    AUTHOR = 'demetoir'

    def generator(self, z, reuse=False, name='generator'):
        with tf.variable_scope(name, reuse=reuse):
            seq = SequenceModel(z)
            seq.add_layer(linear, 4 * 4 * 512)
            seq.add_layer(tf.reshape, [self.batch_size, 4, 4, 512])

            seq.add_layer(conv2d_transpose, [self.batch_size, 8, 8, 256], filter_7722)
            seq.add_layer(bn)
            seq.add_layer(relu)

            seq.add_layer(conv2d_transpose, [self.batch_size, 16, 16, 128], filter_7722)
            seq.add_layer(bn)
            seq.add_layer(relu)

            seq.add_layer(conv2d_transpose, [self.batch_size, 32, 32, self.input_c], filter_7722)
            seq.add_layer(conv2d, self.input_c, filter_5511)
            seq.add_layer(tf.sigmoid)
            net = seq.last_layer

        return net

    def discriminator(self, x, reuse=None, name='discriminator'):
        with tf.variable_scope(name, reuse=reuse):
            seq = SequenceModel(x)
            seq.add_layer(conv2d, 64, filter_5522)
            seq.add_layer(bn)
            seq.add_layer(lrelu)

            seq.add_layer(conv2d, 128, filter_5522)
            seq.add_layer(bn)
            seq.add_layer(lrelu)

            seq.add_layer(conv2d, 256, filter_5522)
            seq.add_layer(bn)
            seq.add_layer(lrelu)

            seq.add_layer(conv2d, 256, filter_5522)
            seq.add_layer(bn)
            seq.add_layer(lrelu)

            seq.add_layer(tf.reshape, [self.batch_size, -1])
            out_logit = seq.add_layer(linear, 1)
            out = seq.add_layer(tf.sigmoid)

        return out, out_logit

    def hyper_parameter(self):
        self.n_noise = 256
        self.batch_size = 64
        self.learning_rate = 0.0002

        self.beta1 = 0.5
        self.disc_iters = 1
        self.lambda_ = 0.25  # The higher value, the more stable, but the slower convergence

    def network(self):
        self.X = tf.placeholder(tf.float32, [self.batch_size] + self.shape_data_x, name='X')
        self.z = tf.placeholder(tf.float32, [self.batch_size, self.n_noise], name='z')

        self.G = self.generator(self.z)
        self.D_real, self.D_real_logit = self.discriminator(self.X)
        self.D_gen, self.D_gene_logit = self.discriminator(self.G, True)

    def loss(self):
        with tf.variable_scope('loss'):
            with tf.variable_scope('loss_D_real'):
                self.loss_D_real = -tf.reduce_mean(self.D_real)

            with tf.variable_scope('loss_D_gen'):
                self.loss_D_gen = tf.reduce_mean(self.D_gen)

                self.loss_D = self.loss_D_real + self.loss_D_gen

        """ Gradient Penalty """
        # This is borrowed from https://github.com/kodalinaveen3/DRAGAN/blob/master/DRAGAN.ipynb
        alpha = tf.random_uniform(shape=[self.batch_size, self.input_h, self.input_w, self.input_c],
                                  minval=0., maxval=1.)
        differences = self.G - self.X  # This is different from MAGAN
        interpolates = self.X + (alpha * differences)
        _, D_inter = self.discriminator(interpolates, reuse=True)
        gradients = tf.gradients(D_inter, [interpolates])[0]
        slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), reduction_indices=[1]))
        gradient_penalty = tf.reduce_mean((slopes - 1.) ** 2)
        with tf.variable_scope('loss', reuse=True):
            with tf.variable_scope('loss_D'):
                self.loss_D += self.lambda_ * gradient_penalty

            with tf.variable_scope('loss_G'):
                self.loss_G = -self.loss_D_gen

    def train_ops(self):
        self.vars_D = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                        scope='discriminator')

        self.vars_G = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                        scope='generator')

        with tf.variable_scope('train_ops'):
            self.train_D = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=self.beta1) \
                .minimize(self.loss_D, var_list=self.vars_D)
            self.train_G = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=self.beta1) \
                .minimize(self.loss_G, var_list=self.vars_G)

        with tf.variable_scope('clip_D_op'):
            self.clip_D_op = [var.assign(tf.clip_by_value(var, -0.01, 0.01)) for var in self.vars_D]

    def misc_ops(self):
        super().misc_ops()
        with tf.variable_scope('misc_ops', reuse=True):
            self.GD_rate = tf.div(tf.reduce_mean(self.loss_G), tf.reduce_mean(self.loss_D))

    def train_model(self, sess=None, iter_num=None, dataset=None):
        self.normal_train(sess, iter_num, dataset)

    def normal_train(self, sess, iter_num, dataset):
        noise = self.get_noise()
        batch_xs = dataset.next_batch(self.batch_size, batch_keys=[BATCH_KEY_TRAIN_X])
        sess.run([self.train_D, self.clip_D_op], feed_dict={self.X: batch_xs, self.z: noise})

        if iter_num % self.disc_iters == 0:
            sess.run(self.train_G, feed_dict={self.z: noise})

        sess.run([self.op_inc_global_step])

    def summary_op(self):
        summary_variable(self.loss_D_gen)
        summary_variable(self.loss_D_real)
        summary_variable(self.loss_D)
        summary_variable(self.loss_G)

        summary_image(self.G, max_outputs=10)
        self.op_merge_summary = tf.summary.merge_all()

    def write_summary(self, sess=None, iter_num=None, dataset=None, summary_writer=None):
        noise = self.get_noise()
        batch_xs = dataset.next_batch(self.batch_size, batch_keys=[BATCH_KEY_TRAIN_X])
        summary, global_step = sess.run([self.op_merge_summary, self.global_step],
                                        feed_dict={self.X: batch_xs, self.z: noise})
        summary_writer.add_summary(summary, global_step)

    def get_noise(self):
        return np.random.uniform(-1.0, 1.0, size=[self.batch_size, self.n_noise])
