# coding: utf-8
import os

from abipy.core.testing import AbipyTest
from abipy.flowtk.tasks import *
from abipy.flowtk.tasks import TaskPolicy, ParalHints

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", 'test_files', "abinit")


class TaskManagerTest(AbipyTest):
    MANAGER = """\
#policy:
#    autoparal: 1
qadapters:
    - priority: 1
      queue:
        qtype: slurm
        qname: Oban
        qparams:
            mail_user: nobody@nowhere
      limits:
        timelimit: 0:20:00
        min_cores: 4
        max_cores: 12
        #condition: {"$eq": {omp_threads: 2}}
      hardware:
        num_nodes: 10
        sockets_per_node: 1
        cores_per_socket: 2
        mem_per_node: 4 Gb
      job:
        modules:
            - intel/compilerpro/13.0.1.117
            - fftw3/intel/3.3
        shell_env:
            PATH: /home/user/tmp_intel13/src/98_main/:/home/user//NAPS/intel13/bin:$PATH
            LD_LIBRARY_PATH: /home/user/NAPS/intel13/lib:$LD_LIBRARY_PATH
        mpi_runner: mpirun
"""
    def test_base(self):
        """
        Simple unit tests for Qadapter subclasses.
        A more complete coverage would require integration testing.
        """
        # Initialize the object from YAML file.
        slurm_manager = TaskManager.from_string(self.MANAGER)

        repr(slurm_manager); str(slurm_manager)
        assert slurm_manager.num_cores == 4
        assert slurm_manager.mpi_procs == 4
        assert slurm_manager.omp_threads == 1
        assert slurm_manager.has_queue

        # Make a simple shell manager that will inherit the initial configuration.
        shell_manager = slurm_manager.to_shell_manager(mpi_procs=1)
        assert shell_manager.mpi_procs == 1
        assert shell_manager.num_cores == 1
        assert not shell_manager.has_queue

        # check that the initial slurm_manger has not been modified
        assert slurm_manager.num_cores == 4

        # Test pickle
        self.serialize_with_pickle(slurm_manager, test_eq=False)

        self.assertMSONable(slurm_manager)

        fixed_manager = slurm_manager.new_with_fixed_mpi_omp(mpi_procs=5, omp_threads=2)
        assert fixed_manager.policy.autoparal == 0
        assert fixed_manager.mpi_procs == 5
        assert fixed_manager.num_cores == 10
        for qad in fixed_manager.qads:
            assert qad.min_cores == 10
            assert qad.max_cores == 10


class ParalHintsTest(AbipyTest):
    def test_base(self):
        """Testing ParalHints."""
        s = \
"""--- !Autoparal
#Autoparal section for Sigma runs.
info:
    autoparal: 1
    max_ncpus: 4
    nkpt: 6
    nsppol: 1
    nspinor: 1
    nbnds: 10
configurations:
    - tot_ncpus: 1
      mpi_ncpus: 1
      efficiency:  1.000000000
      mem_per_cpu:        11.54
      vars: {npfft: 1, npkpt: 1}
    - tot_ncpus: 2
      mpi_ncpus: 2
      efficiency:  1.000000000
      mem_per_cpu:         7.42
      vars: {npfft: 1, npkpt: 2}
    - tot_ncpus: 2
      mpi_ncpus: 2
      efficiency:  0.100000000
      mem_per_cpu:         9.42
      vars: {npfft: 2, npkpt: 1}
    - tot_ncpus: 3
      mpi_ncpus: 3
      efficiency:  0.833333333
      mem_per_cpu:         6.60
      vars: {npfft: 3, npkpt: 1}
    - tot_ncpus: 4
      mpi_ncpus: 4
      efficiency:  0.833333333
      mem_per_cpu:         15.77
      vars: {npfft: 2, npkpt: 2}
...
"""
        tmpfile = self.tmpfile_write(s)

        # Parse the file with the configurations.
        confs = ParalHintsParser().parse(tmpfile)
        str(confs)
        assert confs.max_cores == 4
        assert confs.max_mem_per_proc == 15.77
        assert confs.max_speedup == 3.333333332
        assert confs.max_efficiency == 1.0
        # Test as_dict, from_dict
        ParalHints.from_dict(confs.as_dict())

        # MG: Disabled after refactoring.
        # TODO: Write new units tests
        # Optimize speedup with ncpus <= max_ncpus
        #policy = TaskPolicy(autoparal=1, max_ncpus=3)
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 3)

        # Optimize speedup with ncpus <= max_ncpus and condition on efficiency.
        #policy = TaskPolicy(autoparal=1, max_ncpus=4, condition={"efficiency": {"$ge": 0.9}})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 2)

        # Optimize speedup with ncpus <= max_ncpus and conditions on efficiency and mem_per_cpu.
        #policy = TaskPolicy(autoparal=1, mode="default", max_ncpus=4,
        #                    condition={"$and": [{"efficiency": {"$ge": 0.8}}, {"mem_per_cpu": {"$le": 7.0}}]})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 3)

        # If no configuration satisfies the constraints, we return the conf with the highest speedup.
        #policy = TaskPolicy(autoparal=1, max_ncpus=4, condition={"efficiency": {"$ge": 100}})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 4)

        # Wrong conditions --> dump a warning and return the conf with the highest speedup.
        #policy = TaskPolicy(autoparal=1, max_ncpus=4, condition={"foobar": {"$ge": 100}})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 4)

        # Select configuration with npfft == 1
        #policy = TaskPolicy(autoparal=1, max_ncpus=4, vars_condition={"npfft": {"$eq": 3}})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 3)
        #aequal(optimal.vars["npfft"],  3)

        # Select configuration with npfft == 2 and npkpt == 1
        #policy = TaskPolicy(autoparal=1, max_ncpus=4,
        #                    vars_condition={"$and": [{"npfft": {"$eq": 2}}, {"npkpt": {"$eq": 1}}]})
        #optimal = confs.select_optimal_conf(policy)
        #aequal(optimal.num_cores, 2)
        #aequal(optimal.vars["npfft"],  2)
        #aequal(optimal.vars["npkpt"],  1)
        #assert 0


class AbinitBuildTest(AbipyTest):

    def test_abinit_build(self):
        from abipy.flowtk import AbinitBuild
        build = AbinitBuild()
        str(build)
        assert build.has_netcdf
        #assert not build.has_omp
        #assert build.has_mpi
        #assert build.has_mpiio
        #assert build.has_libxc

        assert build.version_ge("4.0")
        assert build.compare_version(build.version, "==")
        assert build.compare_version(build.version, ">=")
